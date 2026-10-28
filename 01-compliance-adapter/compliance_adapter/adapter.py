import hashlib
import logging
import time

from compliance_logging_sdk.core import ComplianceLogger
from compliance_logging_sdk.ClinicalSession import ClinicalSession
from compliance_logging_sdk.ComplianceObject import ComplianceObject
from compliance_logging_sdk.InferenceResult import InferenceResult
from compliance_logging_sdk.SystemMetadata import SystemMetadata

# bridge between the AI application and the compliance SDK
class ComplianceAdapter:

    # creates a ComplianceLogger for the queue file and remembers model metadata
    def __init__(self, queue_file, model_name, model_version):
        self.logger = ComplianceLogger(queue_file)
        self.model_name = model_name
        self.model_version = model_version
        self.start_time = None
        self.input_hash = None

    # computes a SHA-256 fingerprint of the input
    def start(self, input_bytes):
        self.start_time = time.perf_counter()
        self.input_hash = "sha256-" + hashlib.sha256(input_bytes).hexdigest()

    def finish(self, prediction, confidence=None):
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

    # writes the failure to Python's log, no audit event is produced yet
    def error(self, exception):
        logging.error("Inference failed: %s", exception)