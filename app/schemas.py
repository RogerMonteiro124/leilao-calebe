from pydantic import BaseModel, Field


class ParticipantInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    access_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    fixed_value: int = Field(gt=0)
    status: str = "available"


class ItemInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    display_order: int = 0
    status: str = "waiting"
