from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-4.1-mini"
    openai_review_model: str = "gpt-4.1"
    login_username: str = "thesis"
    login_password_hash: str = ""
    google_client_id: str = ""
    cookie_secure: bool = False
    frontend_origins: str = "http://127.0.0.1:3000,http://localhost:3000"
    database_url: str = "postgresql+psycopg://thesis:CHANGE_ME@localhost:55432/thesis"
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_revision: str = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
    retrieval_metadata_weight: float = Field(default=0.3, ge=0, le=1)
    retrieval_candidates: int = Field(default=50, ge=20, le=200)
    chunk_tokens: int = Field(default=400, ge=16, le=480)
    chunk_overlap: int = Field(default=50, ge=0)
    raw_data_dir: Path = Path("../data/raw")
    hf_home: Path = Path("../data/models")

    @model_validator(mode="after")
    def valid_overlap(self):
        if self.chunk_overlap >= self.chunk_tokens:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_TOKENS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
