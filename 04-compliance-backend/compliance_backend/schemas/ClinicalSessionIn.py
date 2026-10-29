from pydantic import BaseModel

from .InferenceResultIn import InferenceResultIn


# context of a single decision, as it arrives in the request
class ClinicalSessionIn(BaseModel):
    input_data_hash: str                    # sHA-256 fingerprint of the input
    inference_result: InferenceResultIn     # the output of the model
