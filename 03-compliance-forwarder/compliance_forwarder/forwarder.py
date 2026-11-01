import json
import logging
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx

from compliance_forwarder.model.outcome import Outcome

logger = logging.getLogger(__name__)

# reads the jsonl file and parses events to send to backend
class Forwarder:

    def __init__(
        self,
        queue_file: str,
        backend_url: str,
        state_dir: str,
        client: httpx.Client | None = None,
        poll_seconds: float = 1.0,
        backoff_start_seconds: float = 1.0,
        backoff_max_seconds: float = 60.0,
    ) -> None:
        self.queue_file = Path(queue_file)
        self.url = backend_url.rstrip("/") + "/events"
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.cursor_file = self.state_dir / "cursor.txt"
        self.dead_letter_file = self.state_dir / "dead_letter.jsonl"

        self.owns_client = client is None
        self.client = client if client is not None else httpx.Client(timeout=5.0)

        self.poll_seconds = poll_seconds
        self.backoff_start_seconds = backoff_start_seconds
        self.backoff_max_seconds = backoff_max_seconds
        self.failures = 0 

    # the number of lines that were already handled
    def read_cursor(self) -> int:
        if not self.cursor_file.exists():
            return 0
        return int(self.cursor_file.read_text().strip() or 0)

    # keeps track of lines that were written into .tmp
    def save_cursor(self, cursor: int) -> None:
        temporary_file = self.cursor_file.with_suffix(".tmp")
        temporary_file.write_text(str(cursor))
        os.replace(temporary_file, self.cursor_file)

    # the lines that were not handled yet
    def read_new_lines(self, cursor: int) -> list[str]:
        if not self.queue_file.exists():
            return []
        complete_lines = self.queue_file.read_text().split("\n")[:-1]
        return complete_lines[cursor:]

    # a line the backend will never accept is kept here, so it is not lost and does not block the lines behind it
    def dead_letter(self, line: str, reason: str) -> None:
        record = {
            "dead_lettered_at": datetime.now(UTC).isoformat(),
            "reason": reason,
            "line": line,
        }
        with self.dead_letter_file.open("a") as file:
            file.write(json.dumps(record) + "\n")
        logger.error("event dead-lettered: %s", reason)

    # sent (2XX): the backend stored it successfully!
    # retry (5XX): network error or server error, try the same line again later in some time
    # rejected (4XX): the backend refuses to accept the event, repeating would do the same -> deadletter!
    def send(self, line: str) -> Outcome:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            self.dead_letter(line, "not valid json")
            return Outcome.REJECTED

        try:
            response = self.client.post(self.url, json=event)
        except httpx.HTTPError as error:
            logger.warning("backend not reachable: %s", error)
            return Outcome.RETRY

        if response.is_success:
            return Outcome.SENT
        
        if response.is_client_error:
            self.dead_letter(line, f"backend answered {response.status_code}")
            return Outcome.REJECTED

        # account for information (1XX), redirects (3XX) etc
        logger.warning("backend answered %s, will retry", response.status_code)
        return Outcome.RETRY

    # one pass over the new lines, returns how many events the backend stored
    def run_once(self) -> int:
        cursor = self.read_cursor()
        sent = 0

        for line in self.read_new_lines(cursor):
            if line.strip():
                outcome = self.send(line)
                if outcome == Outcome.RETRY:
                    self.failures += 1
                    return sent
                if outcome == Outcome.SENT:
                    sent += 1
            cursor += 1
            self.save_cursor(cursor)

        self.failures = 0
        return sent

    # delay increasing if the backend is TEMPORARILY down
    def next_delay(self) -> float:
        if self.failures == 0:
            return self.poll_seconds
        delay = self.backoff_start_seconds * 2 ** (self.failures - 1)
        return min(delay, self.backoff_max_seconds)

    def run_forever(self, stop: Callable[[], bool] = lambda: False, sleep: Callable[[float], None] = time.sleep,) -> None:
        while not stop():
            self.run_once()
            sleep(self.next_delay())

    def close(self) -> None:
        if self.owns_client:
            self.client.close()
