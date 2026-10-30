from pydantic import BaseModel

from .inference_result import InferenceResult


# context of a single decision
class ClinicalSession(BaseModel):
    input_data_hash: str                # a SHA-256 fingerprint of the input (for example the image)
    inference_result: InferenceResult   # the InferenceResult above
