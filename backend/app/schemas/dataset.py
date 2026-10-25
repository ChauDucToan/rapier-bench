from pydantic import BaseModel, ConfigDict


class DatasetResponse(BaseModel):
    id: str
    name: str
    hf_id: str
    domain: str
    task_type: str
    default_split: str
    evaluator_key: str

    model_config = ConfigDict(from_attributes=True)
