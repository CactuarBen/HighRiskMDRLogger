import hashlib
import logging
import time

from compliance_logging_sdk.core import ComplianceLogger
from compliance_logging_sdk.model.clinical_session import ClinicalSession
from compliance_logging_sdk.model.compliance_object import ComplianceObject
from compliance_logging_sdk.model.inference_result import InferenceResult
from compliance_logging_sdk.model.system_metadata import SystemMetadata

logger = logging.getLogger(__name__)

# bridge between the AI application and the compliance SDK
class ComplianceAdapter:

    # creates a ComplianceLogger for the queue file and remembers model metadata
    def __init__(self, queue_file: str, model_name: str, model_version: str) -> None:
        self.logger = ComplianceLogger(queue_file)
        self.model_name = model_name
        self.model_version = model_version
        self.start_time: float | None = None
        self.input_hash: str | None = None

    # computes a SHA-256 fingerprint of the input
    def start(self, input_bytes: bytes) -> None:
        self.start_time = time.perf_counter()
        self.input_hash = "sha256-" + hashlib.sha256(input_bytes).hexdigest()

    def finish(self, prediction: dict[str, str], confidence: float | None) -> str:
        if self.start_time is None or self.input_hash is None:
            raise RuntimeError("finish() called before start()")

        elapsed_ms = (time.perf_counter() - self.start_time) * 1000

        result = InferenceResult(
            prediction=prediction,
            confidence=confidence,
            execution_time_ms=elapsed_ms,
        )
        session = ClinicalSession(
            input_data_hash=self.input_hash,
            inference_result=result,
        )
        system = SystemMetadata(
            model_name=self.model_name,
            model_version=self.model_version,
        )
        event = ComplianceObject(system=system, clinical_session=session)

        self.logger.write_event(event)
        self.start_time = None
        self.input_hash = None
        return event.event_id

    # writes the failure to Python's log, no audit event is produced yet
    def error(self, exception: BaseException) -> None:
        logger.error("Inference failed: %s", exception)
        self.start_time = None
        self.input_hash = None