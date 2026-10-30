from pydantic import BaseModel


# contains the information about the inference session
class InferenceResult(BaseModel):
    prediction: dict[str,str] = {}      # the output of the mode, saved as dictionary
    confidence: float | None = None     # model's sensitivity, confidence of output
    execution_time_ms: float            # how long the inference process took
