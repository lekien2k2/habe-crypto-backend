from pydantic import BaseModel, Field


class KeyGenRequest(BaseModel):
    master_public_key: str = Field(..., description="Base64-encoded MPK")
    master_secret_key: str = Field(..., description="Base64-encoded MSK")
    attributes: list[str] = Field(
        ...,
        min_length=1,
        description="User attribute set, e.g. ['Manager', 'Dept_A']",
    )
