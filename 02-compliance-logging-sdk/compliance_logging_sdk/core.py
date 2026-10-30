from pathlib import Path

from .model.compliance_object import ComplianceObject


class ComplianceLogger:

    # Set up the logger
    def __init__(self, queue_file: str | Path) -> None:
        self.queue_file = Path(queue_file)
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)

    # Append one event to the queue file as a single line of JSON.
    def write_event(self, event: ComplianceObject) -> None:
        with open(self.queue_file, "a") as f:
            f.write(event.model_dump_json() + "\n")

    # Shut the logger down
    def close(self) -> None:
        pass
