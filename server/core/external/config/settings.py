import json
import logging
from typing import Optional

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


def _load_secret_from_aws(secret_name: str, region: str) -> dict:
    """AWS Secrets Manager에서 시크릿을 조회한다."""
    import boto3

    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])


class Settings(BaseSettings):
    # 로컬 개발 시 .env 파일에서 직접 설정
    DB_HOST: str = "localhost"
    DB_PORT: int = 3307
    DB_USER: str = "root"
    DB_PASSWORD: str = "root"
    DB_NAME: str = "query_repository"

    # AWS Secrets Manager 설정 (운영 환경)
    AWS_SECRET_NAME: Optional[str] = None
    AWS_REGION: str = "ap-northeast-2"

    model_config = {"env_file": ".env", "extra": "ignore"}

    def model_post_init(self, __context) -> None:
        if self.AWS_SECRET_NAME:
            try:
                secret = _load_secret_from_aws(self.AWS_SECRET_NAME, self.AWS_REGION)
                self.DB_HOST = secret.get("MYSQL_HOST", self.DB_HOST)
                self.DB_PORT = int(secret.get("port", self.DB_PORT))
                self.DB_USER = secret.get("MYSQL_USERNAME", self.DB_USER)
                self.DB_PASSWORD = secret.get("MYSQL_PASSWORD", self.DB_PASSWORD)
                self.DB_NAME = secret.get("MYSQL_DATABASE", self.DB_NAME)
                logger.info(
                    "Loaded DB credentials from Secrets Manager: %s",
                    self.AWS_SECRET_NAME,
                )
            except Exception as e:
                logger.error("Failed to load secret '%s': %s", self.AWS_SECRET_NAME, e)
                raise

    @property
    def database_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()
