import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    keys: tuple[str, ...]
    model: str
    database_url: str
    origins: tuple[str, ...]
    simulate: bool


def get_settings() -> Settings:
    keys = tuple(k.strip() for k in os.getenv('LLM_API_KEYS', '').split(',') if k.strip())
    return Settings(
        keys=keys,
        model=os.getenv('LLM_MODEL', 'gemini/gemini-2.0-flash'),
        database_url=os.getenv('DATABASE_URL', 'sqlite:///./app.db'),
        origins=tuple(o.strip() for o in os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(',') if o.strip()),
        simulate=os.getenv('ENABLE_FAILURE_SIMULATION', 'false').lower() == 'true',
    )
