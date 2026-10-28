from typing import Optional

from pydantic import BaseModel

# Contains the information about the inference session
class InferenceResult(BaseModel):
    prediction: dict = {}               # The output of the mode, saved as dictionary
    confidence: Optional[float] = None  # Model's sensitivity, confidence of output
    execution_time_ms: float            # How long the inference process took
