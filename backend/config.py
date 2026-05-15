from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    # S3 Configuration
    S3_BUCKET_STANDARD: str = Field(
        default="habe-standard-storage",
        description="S3 bucket for standard tier",
    )
    S3_BUCKET_ARCHIVE: str = Field(
        default="habe-archive-storage",
        description="S3 bucket for archive tier",
    )
    AWS_REGION: str = Field(default="us-east-1", description="AWS region")

    # API Configuration
    MAX_FILE_SIZE_MB: int = Field(
        default=100, description="Maximum file upload size in MB"
    )
    CORS_ORIGINS: List[str] = Field(
        default=["*"], description="Allowed CORS origins"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Singleton settings instance
settings = Settings()
