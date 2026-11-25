from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)
    system_prompt: str | None = None

    @field_validator('session_id', 'message')
    @classmethod
    def nonblank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('must not be empty')
        return value

    @field_validator('session_id')
    @classmethod
    def session_length(cls, value):
        if len(value) > 128:
            raise ValueError('session_id exceeds 128 characters')
        return value
