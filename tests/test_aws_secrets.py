"""Tests for AWS Secrets Manager password resolution and SSL configuration in backend_ETL."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, unquote, urlparse

from backend_ETL.config import (
    BackendConfig,
    fetch_aws_secret,
    load_backend_config,
)
from backend_ETL.main import parse_args

# ─── fetch_aws_secret ────────────────────────────────────────────────────────────


def test_fetch_aws_secret_json():
    """Verifies parsing of an AWS RDS JSON secret payload."""
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "username": "rds_admin",
                "password": "RdsPassword123!",
                "host": "database-1.cluster-xyz.ap-south-1.rds.amazonaws.com",
                "port": 5432,
                "dbname": "tally_warehouse",
            }
        )
    }

    with patch("boto3.client", return_value=mock_client):
        data = fetch_aws_secret("my-rds-secret", region_name="ap-south-1")
        assert data["username"] == "rds_admin"
        assert data["password"] == "RdsPassword123!"
        assert data["host"] == "database-1.cluster-xyz.ap-south-1.rds.amazonaws.com"
        assert data["dbname"] == "tally_warehouse"


def test_fetch_aws_secret_plain_string():
    """Verifies handling of a plain-text password secret."""
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": "SimpleSecretPass123!"
    }

    with patch("boto3.client", return_value=mock_client):
        data = fetch_aws_secret("plain-secret")
        assert data["password"] == "SimpleSecretPass123!"


# ─── Configuration & Password Assignment ─────────────────────────────────────────


def test_load_backend_config_sets_password_from_secret(tmp_path: Path):
    """Verifies that the secret is fetched and set as postgres_password."""
    cfg_file = tmp_path / "backend_config.json"
    cfg_file.write_text(
        json.dumps(
            {
                "postgres_host": "custom-db-host.rds.amazonaws.com",
                "aws_secret_name": "rds!db-sample",
                "aws_region": "ap-south-1",
            }
        ),
        encoding="utf-8",
    )

    fake_secret = {
        "password": "FetchedPassword456!",
        "username": "postgres",
    }

    with patch("backend_ETL.config.fetch_aws_secret", return_value=fake_secret):
        cfg = load_backend_config(cfg_file)
        # Password comes from AWS secret
        assert cfg.postgres_password == "FetchedPassword456!"
        # Host comes from the config file as requested
        assert cfg.postgres_host == "custom-db-host.rds.amazonaws.com"


# ─── SSL Mode Hardcoded to verify-full & Configurable ssl_root_cert ─────────────


def test_get_dsn_ssl_mode_hardcoded_verify_full():
    """Verifies that sslmode is always verify-full when AWS secret or SSL cert is present."""
    cfg = BackendConfig(
        postgres_host="my-rds.amazonaws.com",
        postgres_user="admin",
        postgres_password="mypassword",
        postgres_db="tally_warehouse",
        aws_secret_name="rds!test",
    )

    dsn = cfg.get_dsn()
    parsed = urlparse(dsn)
    qs = parse_qs(parsed.query)

    assert qs["sslmode"][0] == "verify-full"
    assert "global-bundle.pem" in qs["sslrootcert"][0]


def test_get_dsn_configurable_ssl_root_cert(tmp_path: Path):
    """Verifies that ssl_root_cert can be configured to point to a custom CA bundle."""
    custom_ca = tmp_path / "my-custom-ca.pem"
    custom_ca.write_text("-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----")

    cfg = BackendConfig(
        postgres_host="my-rds.amazonaws.com",
        postgres_user="admin",
        postgres_password="mypassword",
        ssl_root_cert=str(custom_ca),
    )

    dsn = cfg.get_dsn()
    parsed = urlparse(dsn)
    qs = parse_qs(parsed.query)

    assert qs["sslmode"][0] == "verify-full"
    assert str(custom_ca) in qs["sslrootcert"][0]


def test_password_url_encoding():
    """Verifies that passwords with special characters (@, #, :, /) are safely encoded."""
    cfg = BackendConfig(
        postgres_host="rds.amazonaws.com",
        postgres_user="tally_user",
        postgres_password="P@ss:w0rd/#%&=+",
        postgres_db="tally_warehouse",
    )
    dsn = cfg.get_dsn()
    parsed = urlparse(dsn)

    assert parsed.scheme == "postgresql"
    assert parsed.username == "tally_user"
    assert parsed.password == "P%40ss%3Aw0rd%2F%23%25%26%3D%2B"
    assert unquote(parsed.password) == "P@ss:w0rd/#%&=+"


# ─── CLI Arguments ──────────────────────────────────────────────────────────────


def test_parse_args_simple_aws_flags():
    """Verifies parsing of the simplified AWS and SSL CLI flags."""
    argv = [
        "--aws-secret-name",
        "rds!cli-secret",
        "--aws-region",
        "ap-south-1",
        "--ssl-root-cert",
        "/custom/ca.pem",
    ]
    args = parse_args(argv)
    assert args.aws_secret_name == "rds!cli-secret"
    assert args.aws_region == "ap-south-1"
    assert args.ssl_root_cert == "/custom/ca.pem"
