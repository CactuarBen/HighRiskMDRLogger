from pydantic import BaseModel

#  Information about the AI that generated the output
class SystemMetadata(BaseModel):
    model_name: str     # Name of the AI model release
    model_version: str  # Version of the AI model release
