from pydantic import BaseModel


# information about the AI that generated the output, as it arrives in the request
class SystemMetadataIn(BaseModel):
    model_name: str     # name of the AI model release
    model_version: str  # version of the AI model release
