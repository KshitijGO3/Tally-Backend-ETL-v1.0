"""CLI entry point and token management utility for the PostgreSQL backend ETL service."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import uvicorn

from backend_ETL.api import create_app
from backend_ETL.canonical_runner import CanonicalPollerRunner
from backend_ETL.config import fetch_aws_secret, load_backend_config
from backend_ETL.db import PostgresManager
from backend_ETL.logging_setup import setup_logging

# Ensure src/ is on sys.path when executed directly as a script
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

log = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tally PostgreSQL Backend ETL Server & CLI")
    parser.add_argument("--config", type=str, default=None, help="Path to backend JSON config")
    parser.add_argument("--dsn", type=str, default=None, help="PostgreSQL connection DSN")
    parser.add_argument("--host", type=str, default=None, help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=None, help="Bind port (default: 8000)")
    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=None,
        help="Directory where rotating log files will be written",
    )
    parser.add_argument(
        "--bootstrap-only",
        action="store_true",
        help="Bootstrap PostgreSQL tables and exit without starting the HTTP server",
    )
    parser.add_argument(
        "--bootstrap-canonical",
        action="store_true",
        help="Bootstrap Canonical Domain Model (Silver) tables and exit",
    )
    parser.add_argument(
        "--transform-canonical",
        action="store_true",
        help="Execute Canonical Domain Model transformation once and exit",
    )
    parser.add_argument(
        "--company-id",
        type=str,
        default=None,
        help="Company GUID filter for canonical transformation",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Check DB connectivity and per-table row counts, print the report and exit",
    )
    parser.add_argument(
        "--create-token",
        action="store_true",
        help="Generate a new API Bearer token and optional client_id (CLI only)",
    )
    parser.add_argument(
        "--rotate-token",
        action="store_true",
        help="Rotate the API Bearer token for an existing --client-id",
    )
    parser.add_argument(
        "--revoke-token",
        action="store_true",
        help="Revoke the API Bearer token for an existing --client-id",
    )
    parser.add_argument(
        "--client-id",
        type=str,
        default=None,
        help="Client ID for token creation, rotation, or revocation",
    )
    parser.add_argument(
        "--description",
        type=str,
        default=None,
        help="Optional description label when creating a token",
    )
    parser.add_argument(
        "--aws-secret-name",
        type=str,
        default=None,
        help="AWS Secrets Manager secret name or ARN for RDS password",
    )
    parser.add_argument(
        "--aws-region",
        type=str,
        default=None,
        help="AWS region (e.g. ap-south-1, us-east-1)",
    )
    parser.add_argument(
        "--ssl-root-cert",
        type=str,
        default=None,
        help="Path to SSL root CA certificate bundle (e.g. global-bundle.pem)",
    )
    return parser.parse_args(argv)


def run_cli_command(
    db: PostgresManager,
    args: argparse.Namespace,
) -> int | None:
    """Executes CLI-only token management commands if requested."""
    if args.create_token:
        issued = db.issue_token_for_client(
            client_id=args.client_id,
            description=args.description,
            unassigned=(args.client_id is None),
        )
        client_display = (
            issued["client_id"] or "<Unassigned - will be bound on first client registration>"
        )
        print(f"Client ID : {client_display}")
        print(f"API Token : {issued['token']}")
        print("IMPORTANT : Save this token now. Only its SHA-256 hash is stored in PostgreSQL.")
        return 0

    if args.rotate_token:
        if not args.client_id:
            raise ValueError("--client-id is required with --rotate-token")
        rotated = db.rotate_token(args.client_id)
        print(f"Client ID : {rotated['client_id']}")
        print(f"New Token : {rotated['token']}")
        return 0

    if args.revoke_token:
        if not args.client_id:
            raise ValueError("--client-id is required with --revoke-token")
        revoked = db.revoke_token(args.client_id)
        if not revoked:
            print(f"No token found for client_id '{args.client_id}'")
            return 1
        print(f"Revoked token for Client ID: {args.client_id}")
        return 0

    return None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = load_backend_config(args.config)

    if args.dsn:
        cfg.postgres_dsn = args.dsn
    if args.host:
        cfg.backend_host = args.host
    if args.port:
        cfg.backend_port = args.port
    if args.log_level:
        cfg.log_level = args.log_level
    if args.log_dir:
        cfg.log_dir = args.log_dir
    if args.aws_secret_name:
        cfg.aws_secret_name = args.aws_secret_name
        secret_data = fetch_aws_secret(
            cfg.aws_secret_name, region_name=args.aws_region or cfg.aws_region
        )
        if "password" in secret_data:
            cfg.postgres_password = secret_data["password"]
    if args.aws_region:
        cfg.aws_region = args.aws_region
    if args.ssl_root_cert:
        cfg.ssl_root_cert = args.ssl_root_cert

    # Initialize structured rotating logging matching the Tally replication standard
    setup_logging(
        process_name="backend_etl",
        log_dir=cfg.log_dir or None,
        level=cfg.log_level or logging.INFO,
    )
    log.info("Backend ETL initialized (version: 1.0.0, standalone server mode)")

    log.info(
        "Effective config: host=%s port=%s db=%s user=%s dsn_override=%s log_level=%s",
        cfg.postgres_host,
        cfg.postgres_port,
        cfg.postgres_db,
        cfg.postgres_user,
        bool(cfg.postgres_dsn),
        cfg.log_level,
    )

    db = PostgresManager(dsn=cfg.get_dsn())

    if args.diagnose:
        report = db.diagnose_data()
        print(report)
        db.close()
        return 0 if report["connected"] else 1

    db.bootstrap()

    cli_exit_code = run_cli_command(db, args)
    if cli_exit_code is not None:
        db.close()
        return cli_exit_code

    if args.bootstrap_only:
        log.info("PostgreSQL core schema bootstrap completed successfully.")
        db.close()
        return 0

    if args.bootstrap_canonical:
        db.bootstrap_canonical()
        log.info("Canonical Domain Model schema bootstrap completed successfully.")
        db.close()
        return 0

    if args.transform_canonical:
        db.bootstrap_canonical()
        """The Polling Runner is AI Generated."""
        runner = CanonicalPollerRunner(db=db, cfg=cfg.etl)
        results = runner.run_once(company_id=args.company_id)
        print(f"Canonical Transformation Completed: {results}")
        db.close()
        return 0

    # Ensure canonical silver schema exists before server startup
    db.bootstrap_canonical()

    db.diagnose_data()

    app = create_app(db=db, config=cfg, start_poller=True)
    log.info("Starting Backend ETL API server on %s:%d", cfg.backend_host, cfg.backend_port)
    try:
        uvicorn.run(app, host=cfg.backend_host, port=cfg.backend_port)
    finally:
        log.info("Backend ETL API server shut down.")
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
