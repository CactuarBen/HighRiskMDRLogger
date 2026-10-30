from pydantic import BaseModel


# the model output as it arrives in the request
# mirrors the SDK's InferenceResult, but is declared here so the backend does not import the SDK
class InferenceResultIn(BaseModel):
    prediction: dict[str, str] = {}     # the output of the model, saved as dictionary
    confidence: float | None            # confidence of the output, some models give none
    execution_time_ms: float            # how long the inference took
