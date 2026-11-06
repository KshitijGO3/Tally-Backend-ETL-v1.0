"""Configuration loader for the PostgreSQL backend ETL service."""

from __future__ import annotations

import json
import logging
import os
import boto3

import urllib.parse
from pathlib import Path

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

_DEFAULT_CERT = Path(__file__).resolve().parent / "global-bundle.pem"


def fetch_aws_secret(secret_name: str, region_name: str = "") -> dict[str, str]:
    """Fetches a secret string or JSON payload from AWS Secrets Manager."""

    client = boto3.client("secretsmanager", region_name=region_name or None)
    response = client.get_secret_value(SecretId=secret_name)
    secret_str = response.get("SecretString", "")
    try:
        data = json.loads(secret_str)
        if isinstance(data, dict):
            return {k: str(v) for k, v in data.items()}
    except json.JSONDecodeError:
        pass
    return {"password": secret_str}


class ETLConfig(BaseModel):
    """Configuration for Canonical Domain Model transformation."""

    enabled: bool = True
    execution_mode: str = "polling"  # "polling" | "manual"
    polling_interval_seconds: int = 30
    max_batch_vouchers: int = 2000


class BackendConfig(BaseModel):
    """Runtime settings for the PostgreSQL backend API server."""

    postgres_dsn: str = ""
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "admin"
    postgres_db: str = "tally_warehouse"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    log_level: str = "INFO"
    log_dir: str = ""
    etl: ETLConfig = Field(default_factory=ETLConfig)

    # AWS Secrets Manager & SSL configuration
    aws_secret_name: str = ""
    aws_region: str = ""
    ssl_root_cert: str = ""

    # Ollama Conversational AI Assistant
    ollama_model: str = "qwen2.5:7b"
    ollama_host: str = "http://localhost:11434"

    def resolve_ssl_cert(self) -> Path | None:
        """Returns the path to the SSL root certificate if configured or present."""
        if self.ssl_root_cert:
            p = Path(self.ssl_root_cert).resolve()
            if p.is_file():
                return p
        if _DEFAULT_CERT.is_file():
            return _DEFAULT_CERT
        return None

    def get_dsn(self) -> str:
        """Returns the PostgreSQL connection string (DSN)."""
        if self.postgres_dsn:
            return self.postgres_dsn

        user = urllib.parse.quote(self.postgres_user, safe="")
        password = urllib.parse.quote(self.postgres_password, safe="")
        dsn = f"postgresql://{user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

        cert = self.resolve_ssl_cert()
        # SSL mode is always verify-full when connecting with an SSL root cert or AWS secret
        if cert and (self.aws_secret_name or self.ssl_root_cert):
            dsn += f"?sslmode=verify-full&sslrootcert={urllib.parse.quote(str(cert))}"

        return dsn


def load_backend_config(config_path: str | Path | None = None) -> BackendConfig:
    """Loads BackendConfig from an optional JSON file and environment variables."""
    cfg = BackendConfig()
    if config_path is not None:
        path = Path(config_path)
        if path.exists():
            content = path.read_text(encoding="utf-8").strip()
            if content:
                cfg = BackendConfig.model_validate_json(content)
                log.info("Loaded backend configuration from file: %s", path)

    # Environment variables take precedence
    if os.environ.get("POSTGRES_DSN"):
        cfg.postgres_dsn = os.environ["POSTGRES_DSN"]
    if os.environ.get("POSTGRES_HOST"):
        cfg.postgres_host = os.environ["POSTGRES_HOST"]
    if os.environ.get("POSTGRES_PORT"):
        cfg.postgres_port = int(os.environ["POSTGRES_PORT"])
    if os.environ.get("POSTGRES_USER"):
        cfg.postgres_user = os.environ["POSTGRES_USER"]
    if os.environ.get("POSTGRES_PASSWORD"):
        cfg.postgres_password = os.environ["POSTGRES_PASSWORD"]
    if os.environ.get("POSTGRES_DB"):
        cfg.postgres_db = os.environ["POSTGRES_DB"]
    if os.environ.get("BACKEND_HOST"):
        cfg.backend_host = os.environ["BACKEND_HOST"]
    if os.environ.get("BACKEND_PORT"):
        cfg.backend_port = int(os.environ["BACKEND_PORT"])
    if os.environ.get("BACKEND_LOG_LEVEL"):
        cfg.log_level = os.environ["BACKEND_LOG_LEVEL"]
    if os.environ.get("BACKEND_LOG_DIR"):
        cfg.log_dir = os.environ["BACKEND_LOG_DIR"]

    # AWS Secret & SSL
    if os.environ.get("AWS_SECRET_NAME"):
        cfg.aws_secret_name = os.environ["AWS_SECRET_NAME"]
    if os.environ.get("AWS_REGION"):
        cfg.aws_region = os.environ["AWS_REGION"]
    if os.environ.get("SSL_ROOT_CERT"):
        cfg.ssl_root_cert = os.environ["SSL_ROOT_CERT"]

    # Ollama settings
    if os.environ.get("OLLAMA_MODEL"):
        cfg.ollama_model = os.environ["OLLAMA_MODEL"]
    if os.environ.get("OLLAMA_HOST"):
        cfg.ollama_host = os.environ["OLLAMA_HOST"]

    # Canonical ETL settings
    if os.environ.get("BACKEND_ETL_ENABLED"):
        cfg.etl.enabled = os.environ["BACKEND_ETL_ENABLED"].strip().lower() in ("true", "1", "yes")
    if os.environ.get("BACKEND_ETL_EXECUTION_MODE"):
        cfg.etl.execution_mode = os.environ["BACKEND_ETL_EXECUTION_MODE"].strip().lower()
    if os.environ.get("BACKEND_ETL_POLLING_INTERVAL_SECONDS"):
        cfg.etl.polling_interval_seconds = int(os.environ["BACKEND_ETL_POLLING_INTERVAL_SECONDS"])
    if os.environ.get("BACKEND_ETL_MAX_BATCH_VOUCHERS"):
        cfg.etl.max_batch_vouchers = int(os.environ["BACKEND_ETL_MAX_BATCH_VOUCHERS"])

    # If AWS secret name is configured, fetch password from AWS Secrets Manager
    if cfg.aws_secret_name and not os.environ.get("POSTGRES_PASSWORD"):
        try:
            secret_data = fetch_aws_secret(cfg.aws_secret_name, region_name=cfg.aws_region)
            if "password" in secret_data:
                cfg.postgres_password = secret_data["password"]
            # If host was not set or left at default localhost, use host from secret if available
            if secret_data.get("host") and cfg.postgres_host == "localhost":
                cfg.postgres_host = secret_data["host"]
            if secret_data.get("username") and cfg.postgres_user == "postgres":
                cfg.postgres_user = secret_data["username"]
            if secret_data.get("dbname") and cfg.postgres_db == "tally_warehouse":
                cfg.postgres_db = secret_data["dbname"]
            log.info(
                "Successfully fetched database password from AWS Secrets Manager '%s'",
                cfg.aws_secret_name,
            )
        except Exception as e:
            log.error("Failed to fetch AWS secret '%s': %s", cfg.aws_secret_name, e)
            raise

    masked_user = cfg.postgres_user or "postgres"
    log.debug(
        "Config ready: host=%s, port=%d, db=%s, user=%s, log_level=%s",
        cfg.postgres_host,
        cfg.postgres_port,
        cfg.postgres_db,
        masked_user,
        cfg.log_level,
    )
    return cfg
