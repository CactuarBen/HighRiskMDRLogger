from pydantic import BaseModel


#  information about the AI that generated the output
class SystemMetadata(BaseModel):
    model_name: str     # name of the AI model release
    model_version: str  # version of the AI model release
