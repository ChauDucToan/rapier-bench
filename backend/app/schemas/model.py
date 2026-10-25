from pydantic import BaseModel, ConfigDict


class ModelResponse(BaseModel):
    id: str
    name: str
    hf_id: str
    revision: str
    parameters: int
    context_length: int
    torch_dtype: str
    vram_weight_gb: float
    trust_remote_code: bool
    license: str

    model_config = ConfigDict(from_attributes=True)
