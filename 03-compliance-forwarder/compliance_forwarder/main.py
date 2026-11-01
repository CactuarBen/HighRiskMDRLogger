import argparse
import logging

from .forwarder import Forwarder

logger = logging.getLogger(__name__)

def main() -> None:
    parser = argparse.ArgumentParser(description="send the events of the SDK queue file to the backend")
    parser.add_argument("--queue-file", required=True, help="the file the SDK writes to")
    parser.add_argument("--backend-url", default="http://localhost:8000")
    parser.add_argument("--state-dir", default="forwarder_state", help="where the cursor and dead letters are kept")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    forwarder = Forwarder(args.queue_file, args.backend_url, args.state_dir)
    try:
        forwarder.run_forever()
    except KeyboardInterrupt:
        logger.info("stopped")
    finally:
        forwarder.close()


if __name__ == "__main__":
    main()
