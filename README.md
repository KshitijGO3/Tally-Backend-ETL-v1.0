# Tally Backend ETL Service

A high-performance, asynchronous FastAPI backend service and PostgreSQL warehouse for ingesting, storing, and transforming multi-tenant **Tally ERP 9 / TallyPrime** replication data into the **Canonical Domain Model (Silver Layer)**.

---

## Table of Contents

1. [Architecture & Ingestion Topology](#1-architecture--ingestion-topology)
2. [Prerequisites & Database Setup](#2-prerequisites--database-setup)
   - [UTF8 Encoding & en_US.UTF-8 Collation](#21-utf8-encoding--en_usutf-8-collation)
   - [Database Creation Methods](#22-database-creation-methods)
3. [Installation](#3-installation)
4. [Configuration](#4-configuration)
   - [Option A: AWS RDS & Secrets Manager (Recommended for EC2)](#option-a-aws-rds--secrets-manager-recommended-for-ec2)
   - [Option B: Environment Variables](#option-b-environment-variables)
   - [Option C: JSON Configuration File](#option-c-json-configuration-file)
   - [Option D: Command-Line Flags](#option-d-command-line-flags)
   - [Ollama Conversational AI Settings (Optional)](#41-ollama-conversational-ai-settings-optional)
5. [Running the Service](#5-running-the-service)
   - [Starting the API Server](#51-starting-the-api-server)
   - [Schema Bootstrapping Commands](#52-schema-bootstrapping-commands)
   - [On-Demand Canonical Transformation](#53-on-demand-canonical-transformation)
   - [Database Layer (SQLAlchemy 2.0)](#54-database-layer-sqlalchemy-20)
6. [Multi-Tenant Security & Client Provisioning](#6-multi-tenant-security--client-provisioning)
   - [3-Way Match Security Model](#61-3-way-match-security-model)
   - [CLI Token Provisioning Utility](#62-cli-token-provisioning-utility)
   - [Client & Company Onboarding Workflow](#63-client--company-onboarding-workflow)
7. [Canonical Domain Model (Silver Layer) & Transformation Engine](#7-canonical-domain-model-silver-layer--transformation-engine)
   - [Medallion Flow (Bronze to Silver)](#71-medallion-flow-bronze-to-silver)
   - [Universal Date Standard (DD-MM-YYYY)](#72-universal-date-standard-dd-mm-yyyy)
   - [Transformation Engine & Hierarchy Resolution](#73-transformation-engine--hierarchy-resolution)
   - [Autonomous Background Poller & Advisory Locks](#74-autonomous-background-poller--advisory-locks)
   - [ETL Configuration Reference](#75-etl-configuration-reference)
8. [Executive Dashboard & 'Ask O3' AI Assistant](#8-executive-dashboard--ask-o3-ai-assistant)
   - [Executive Frontend Architecture (Vanilla HTML/Tailwind/JS)](#81-executive-frontend-architecture-vanilla-htmltailwindjs)
   - [2×2 Executive KPI Cards & Daily Rollup Engine](#82-22-executive-kpi-cards--daily-rollup-engine)
   - [Single-Thread 'Ask O3' Conversational AI (Ollama)](#83-single-thread-ask-o3-conversational-ai-ollama)
   - [Argon2id Authentication & Multi-Tenant User Management](#84-argon2id-authentication--multi-tenant-user-management)
   - [Launching the Dashboard](#85-launching-the-dashboard)
9. [REST API Reference](#9-rest-api-reference)
   - [Replication Ingestion Endpoints](#91-replication-ingestion-endpoints)
   - [Authentication & User Endpoints](#92-authentication--user-endpoints)
   - [Analytics & Executive KPI Endpoints](#93-analytics--executive-kpi-endpoints)
   - [Ask O3 Conversational Agent Endpoints](#94-ask-o3-conversational-agent-endpoints)
10. [Logging & Production Deployment](#10-logging--production-deployment)
    - [Logging Architecture](#101-logging-architecture)
    - [Linux Systemd Service Setup](#102-linux-systemd-service-setup)
11. [Testing & Verification](#11-testing--verification)

---

## 1. Architecture & Ingestion Topology

Tally Backend ETL serves as the central server for distributed Tally Worker clients:

```
┌───────────────────────────────────────┐         ┌───────────────────────────────────────┐
│       Client Machines (On-Premise)    │         │       Executive Web & Mobile Users    │
│  ┌────────────────┐ ┌────────────────┐│         │  ┌─────────────────────────────────┐  │
│  │ Tally Worker 1 │ │ Tally Worker 2 ││         │  │ O3 Executive Dashboard (Vanilla)│  │
│  └───────┬────────┘ └────────┬───────┘│         │  │ HTML5, Tailwind CSS, ES6+ JS    │  │
└──────────┼───────────────────┼────────┘         │  └────────────────┬────────────────┘  │
           │ HTTPS REST        │ HTTPS REST       └───────────────────┼───────────────────┘
           │ (Bearer Token)    │ (Bearer Token)                       │ HTTPS (JWT)
┌──────────▼───────────────────▼──────────────────────────────────────▼───────────────────┐
│                           Tally Backend ETL (EC2 / Server)                              │
│  ┌─────────────────────────────────┐            ┌────────────────────────────────────┐  │
│  │ FastAPI REST Ingestion Engine   │            │ Ask O3 Assistant & Analytics API   │  │
│  │ - 3-Way Match Tenant Security   │            │ - Executive KPIs & DSO Benchmark   │  │
│  │ - Atomic Voucher & Child Legs   │            │ - Single-Thread Chat History       │  │
│  │ - Raw Staging Tables (Bronze)   │            │ - Ollama (qwen2.5:7b / llama3.2)   │  │
│  └────────────────┬────────────────┘            └─────────────────┬──────────────────┘  │
│                   │ Pure Python ELT                               │ Analytics Queries   │
│  ┌────────────────▼────────────────┐                              │                     │
│  │ Canonical Transformation Engine │                              │                     │
│  │ - Traverses Account Hierarchies │                              │                     │
│  │ - Resolves Custom Voucher Types │                              │                     │
│  │ - Pure DD-MM-YYYY Dates         │                              │                     │
│  │ - 27 Canonical Objects (Silver) │                              │                     │
│  │ - Daily Movements Rollup Engine ├──────────────────────────────┘                     │
│  └────────────────┬────────────────┘                                                    │
│                   │ SQLAlchemy 2.0 (psycopg)                                            │
│  ┌────────────────▼────────────────┐                                                    │
│  │ PostgreSQL 14+ (Amazon RDS)     │                                                    │
│  │ - UTF8 / en_US.UTF-8            │                                                    │
│  │ - canonical_daily_movements     │                                                    │
│  │ - users, user_companies, chat   │                                                    │
│  └─────────────────────────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Prerequisites & Database Setup

### 2.1 UTF8 Encoding & en_US.UTF-8 Collation

Tally data contains Unicode text including Indian Rupee currency symbols (`₹`), multilingual company and ledger names, and regional address formats. Setting `WITH ENCODING = 'UTF8'`, `LC_COLLATE = 'en_US.UTF-8'`, and `LC_CTYPE = 'en_US.UTF-8'` guarantees consistent cross-platform collation, sorting, and full Unicode fidelity without encoding errors.

### 2.2 Database Creation Methods

Before starting the server or running migrations, create the database using `TEMPLATE = template0` to avoid template collation conflicts:

#### Method 1: Using SQL (`psql` or Query Tool)
```sql
CREATE DATABASE tally_warehouse
    WITH TEMPLATE = template0
         ENCODING = 'UTF8'
         LC_COLLATE = 'en_US.UTF-8'
         LC_CTYPE = 'en_US.UTF-8';
```

> **Note for Windows Native PostgreSQL:** If `en_US.UTF-8` is not recognized by Windows, use `LC_COLLATE = 'English_United States.utf8'` or `LC_COLLATE = 'C'`.

#### Method 2: Using the PostgreSQL `createdb` CLI
```bash
createdb -U postgres -h localhost -p 5432 -T template0 -E UTF8 --lc-collate=en_US.UTF-8 --lc-ctype=en_US.UTF-8 tally_warehouse
```

---

## 3. Installation

Clone or deploy the project to your server environment:

```bash
cd "/path/to/Tally Backend ETL v1.0"

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: .env\Scriptsctivate

# Install dependencies in editable mode
pip install -e ".[dev]"
```

---

## 4. Configuration

Connection details can be supplied through any of the following methods (in priority order):

### Option A: AWS RDS & Secrets Manager (Recommended for EC2)

When running on Amazon EC2 connected to Amazon RDS PostgreSQL, credentials are automatically retrieved from AWS Secrets Manager and connected over TLS:

Create `backend_config.json`:
```json
{
  "postgres_host": "database-1.cluster-xyz.ap-south-1.rds.amazonaws.com",
  "postgres_user": "postgres",
  "postgres_db": "tally_warehouse",
  "aws_secret_name": "arn:aws:secretsmanager:ap-south-1:123456789012:secret:rds-db-credentials",
  "aws_region": "ap-south-1",
  "ssl_root_cert": "global-bundle.pem"
}
```

### Option B: Environment Variables (Recommended for Docker / Containers)

```bash
export POSTGRES_HOST="localhost"
export POSTGRES_PORT="5432"
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="your_secure_password"
export POSTGRES_DB="tally_warehouse"
export BACKEND_HOST="0.0.0.0"
export BACKEND_PORT="8000"

# Optional: Ollama Conversational AI
export OLLAMA_MODEL="qwen2.5:7b"
export OLLAMA_HOST="http://localhost:11434"
```

### Option C: JSON Configuration File

```json
{
  "postgres_host": "localhost",
  "postgres_port": 5432,
  "postgres_user": "postgres",
  "postgres_password": "your_password",
  "postgres_db": "tally_warehouse",
  "backend_host": "0.0.0.0",
  "backend_port": 8000,
  "ollama_model": "qwen2.5:7b",
  "ollama_host": "http://localhost:11434"
}
```

### Option D: Command-Line Flags

```bash
backend-etl --dsn "postgresql://postgres:password@localhost:5432/tally_warehouse" --port 8000
```

### 4.1 Ollama Conversational AI Settings (Optional)

Ollama is **strictly optional** to launch and use the application. The executive dashboard and chat assistant function out of the box with zero external AI dependencies via an autonomous deterministic Python analytics router.

When local Ollama is available, you can configure it via `backend_config.json` or environment variables:

| Setting | Environment Variable | Default Value | Description |
|---|---|---|---|
| `ollama_model` | `OLLAMA_MODEL` | `qwen2.5:7b` | Model name (e.g. `qwen2.5:7b`, `llama3.2:3b`, `mistral`) |
| `ollama_host` | `OLLAMA_HOST` | `http://localhost:11434` | URL of local or remote Ollama instance |

> **Graceful Fallback:** If Ollama is offline or unreachable, calls automatically time out after 3.0s and fall back cleanly to deterministic analytical queries (Sales, Collections, DSO payment delays, and Unpaid Invoices) directly from PostgreSQL.

---

## 5. Running the Service

### 5.1 Starting the API Server

```bash
# Using CLI entrypoint:
backend-etl --config backend_config.json

# Or directly with Python:
py src/backend_ETL/main.py --config backend_config.json
```

On startup, the server automatically:
1. Creates any missing Bronze raw staging tables (from the SQLAlchemy models).
2. Creates any missing 27 Canonical Silver tables and sync cursors.
3. Launches the autonomous background transformation poller thread.
4. Starts the Uvicorn ASGI server on the configured host/port.

### 5.2 Schema Bootstrapping Commands

```bash
# Bootstrap Bronze raw ingestion schema and exit:
backend-etl --bootstrap-only

# Bootstrap 27 Canonical Silver tables and exit:
backend-etl --bootstrap-canonical
```

### 5.3 On-Demand Canonical Transformation

```bash
# Transform all companies:
backend-etl --transform-canonical

# Transform a specific company GUID:
backend-etl --transform-canonical --company-id "comp-guid-001"
```

### 5.4 Database Layer (SQLAlchemy 2.0)

All database access goes through SQLAlchemy 2.0 (ORM models plus `select()` / `insert()` statements) on the `psycopg` v3 driver. Application code contains no raw SQL strings, apart from the one-line `VoucherType` view created in `bootstrap()`.

| Piece | Location |
|---|---|
| Declarative models (53 tables: app, bronze/Tally, canonical) | `src/backend_ETL/models/` |
| Engine and session factory | `src/backend_ETL/database.py` |
| Data access layer | `PostgresManager` in `src/backend_ETL/db.py` |
| Column-coercion metadata for replication payloads | `TableSpec` in `schema.py`, `CANONICAL_TABLE_SPECS` in `canonical_runner.py` |

Use `with db.session() as s:` for database work: it is one transaction that commits on success and rolls back on any exception.

**Schema creation.** `bootstrap()` and `bootstrap_canonical()` run `Base.metadata.create_all()`, which creates only *missing* tables and indexes. There is no Alembic, so changing the columns of an existing table needs a manual `ALTER TABLE`. `tests/test_schema_snapshot.py` fails whenever a model changes without `tests/schema_snapshot.json` being regenerated (the command is at the bottom of that test file).

**Adding a table.**
1. Add a model class in `models/app_tables.py`, `tally_tables.py` or `canonical_tables.py`.
2. If it is looked up by name, register it in `MASTER_MODELS`, `CHILD_MODELS` or `CANONICAL_MODELS` in `models/__init__.py`.
3. If it takes part in replication or the canonical transform, add its `TableSpec` (bronze) or `CANONICAL_TABLE_SPECS` entry (canonical).
4. Regenerate `tests/schema_snapshot.json`.

**Dependencies.** `sqlalchemy>=2.0.30` and `psycopg[binary]>=3.1`. The psycopg connection pool is no longer used; pooling is SQLAlchemy's (10 connections, or none when `use_pool=False`).

**Known issues.** Problems found during the migration were deliberately not fixed; see [`specs/sqlalchemy_bug_register.md`](specs/sqlalchemy_bug_register.md).

---

## 6. Multi-Tenant Security & Client Provisioning

### 6.1 3-Way Match Security Model

Every incoming API request must satisfy 3-way tenant isolation:
1. `Authorization: Bearer <token>` header (validated against SHA-256 hash in `api_tokens`).
2. `client_id` query parameter (token must be bound to this client).
3. `company_id` query parameter (company must be mapped to this client in `client_company_mapping`).

Any violation immediately returns **`403 Forbidden`**.

### 6.2 CLI Token Provisioning Utility

Tokens are strictly generated and managed on the server:

```bash
# Generate unassigned token for client self-onboarding:
backend-etl --create-token --description "Client Onboarding Token"

# Generate token pre-assigned to a specific client_id:
backend-etl --create-token --client-id "client-uuid-001" --description "Client 001 Token"

# Rotate token for an existing client:
backend-etl --rotate-token --client-id "client-uuid-001"

# Revoke token immediately:
backend-etl --revoke-token --client-id "client-uuid-001"
```

### 6.3 Client & Company Onboarding Workflow

1. **Client Registration (`POST /api/v1/clients`):**
   Client exchanges the unassigned token to register client metadata and permanently bind the token to their `client_id`.
2. **Company Mapping (`POST /api/v1/companies`):**
   Client registers company metadata (`guid`, `name`, `books_from`), linking the company to their tenant account.
3. **Replication Sync:**
   Client transmits masters, vouchers, and child entries via `/api/v1/sync/batch` or `/api/v1/vouchers/batch`.

---

## 7. Canonical Domain Model (Silver Layer) & Transformation Engine

### 7.1 Medallion Flow (Bronze to Silver)

Raw tables replicate Tally's exact XML structure. The transformation engine cleans, types, and converts raw data into analytics-ready canonical models:
- **Raw Bronze:** `vouchers`, `ledger_entries`, `inventory_entries`, `ledgers`, `groups`
- **Silver Canonical:** `canonical_general_ledger`, `canonical_accounts`, `canonical_bill_events`, `canonical_inventory_movements`, etc.

### 7.2 Universal Date Standard (Native SQL DATE in Silver, DD-MM-YYYY in UI Presentation)

All temporal columns across the Silver canonical schema are stored as native PostgreSQL `DATE` types (`YYYY-MM-DD`). This enables:
- High-performance indexed B-Tree range scans (`WHERE date >= '2024-10-01' AND date <= '2024-10-15'`).
- Accurate chronological comparison and sorting (`ORDER BY date DESC`).
- Direct SQL temporal pushdowns without requiring full table scans or string parsing in Python.

**Boundary Ingestion Conversion:**
Bronze staging tables preserve raw Tally date formats (`YYYYMMDD`, `DD-Mon-YYYY`, `DD/MM/YYYY`, etc.). During ETL Bronze-to-Silver transformation, `backend_ETL.date_utils.parse_tally_date()` parses raw strings directly into native Python `datetime.date` objects. Tally sentinel/dummy dates (`19000101`, `00000000`, `0`, `0-0-0`, `1900-01-01`) are converted to SQL `NULL` to prevent corrupted aging analysis.

**API & UI Presentation:**
When serving analytics and dashboard consumers, dates are formatted into standard Indian business format **`DD-MM-YYYY`** (e.g. `15-10-2024`) via `backend_ETL.date_utils.format_canonical_date()`.

### 7.3 Transformation Engine & Hierarchy Resolution

- **Group Traversal:** Recursively walks parent group hierarchies to classify accounts into `customer`, `supplier`, `bank`, `cash`, `tax`, `expense`, or `income`.
- **Custom Voucher Type Hierarchy Climbing:** Recursively walks custom voucher types in Python memory to resolve custom types (e.g. `Tax Invoice`, `Export Sales`, `Special Receipt`) to their canonical primary Tally types (`Sales`, `Receipt`, `Purchase`, `Payment`, `Credit Note`, `Debit Note`, `Journal`, `Contra`), populating `base_type` on `canonical_voucher_types` and `canonical_vouchers`.
- **Daily Movements Rollup Engine:** Idempotently calculates daily aggregations across date, base voucher type, account classification role, and debit/credit in pure Python memory without database triggers or stored procedures, upserting directly into `canonical_daily_movements` at the completion of each sync run.
- **Decoupled Bill Events:** Separates double-entry accounting legs (`canonical_postings`) from bill settlement allocations (`canonical_bill_events`).
- **PII Decoupling:** Isolates sensitive contact details into `canonical_account_contacts`.

### 7.4 Autonomous Background Poller & Advisory Locks

- Transformation runs in an independent background worker thread polling every 30 seconds.
- Uses PostgreSQL transactional advisory locks:
  `SELECT pg_try_advisory_xact_lock(hashtext('canonical_elt_' || company_id)::bigint);`
  Guarantees zero concurrency race conditions even across multi-process or clustered deployments.

### 7.5 ETL Configuration Reference

Configure inside `backend_config.json` under the `"etl"` block:

| Setting | Environment Variable | Default | Description |
|---|---|---|---|
| `enabled` | `BACKEND_ETL_ENABLED` | `true` | Enable/disable transformation engine |
| `execution_mode` | `BACKEND_ETL_EXECUTION_MODE` | `polling` | `polling` (background) or `manual` |
| `polling_interval_seconds` | `BACKEND_ETL_POLLING_INTERVAL_SECONDS` | `30` | Interval between delta checks |
| `max_batch_vouchers` | `BACKEND_ETL_MAX_BATCH_VOUCHERS` | `2000` | Chunk size per incremental pass |

---

## 8. Executive Dashboard & 'Ask O3' AI Assistant

The system includes an executive web and mobile frontend matching the O3 design specifications (`UI Samples/o3_agent_web_home.jpeg` and `UI Samples/o3_agent_mob_home.jpeg`), providing business leaders with real-time financial intelligence from their Tally ERP data.

### 8.1 Executive Frontend Architecture (Vanilla HTML/Tailwind/JS)

All frontend code lives under [`src/frontend_dashboard`](src/frontend_dashboard) and adheres to strict lightweight architectural constraints:
- **Zero Node/React Dependencies:** Pure vanilla HTML5, modern Tailwind CSS (via CDN), and vanilla ES6+ JavaScript.
- **Two Focused Pages:**
  - **Login & Onboarding (`/login`):** Executive card with organization registration and secure sign-in.
  - **Executive Dashboard (`/dashboard`):** 2×2 KPI cards, dynamic greeting, period selector, company switcher, and continuous conversational AI panel.
- **Desktop & Mobile Responsive:**
  - **Desktop:** Dark left navigation rail (`#0b0f19`) with O3 logo and user avatar (`MK`), 2-column layout with persistent Ask O3 chat panel.
  - **Mobile:** Clean mobile header and sliding bottom sheet drawer for the Ask O3 assistant.

### 8.2 2×2 Executive KPI Cards & Dynamic Date Range Filters

The dashboard displays 4 core financial KPIs queried directly from the `canonical_daily_movements` table:
1. **Sales:** Total revenue for the period with period-over-period percentage comparison (e.g., `↑ 18% vs 1st to 26th September`). Formatted in Indian denominations (`₹ 1.84 Cr`, `₹ 45.20 L`).
2. **Collections:** Total receipts into cash and bank accounts with prior period comparison (e.g., `↑ 9% vs 1st to 26th September`) and customer count.
3. **Receivables:** Net customer outstanding balance as of the latest transaction date (e.g., `as of 26 Oct`).
4. **Purchases:** Total vendor procurement for the period with prior period comparison (e.g., `↓ 6% vs 1st to 26th September`).

#### Date Range Filter Controls:
- **Default Filter (Dynamic Month-to-Date):**
  - When the user logs in today (e.g., 26th October), the filter automatically defaults to Month-to-date and displays **`1st to 26th October`** dynamically anchored to today's date.
- **5 Default Presets + 1 Custom Date Range:**
  1. **Month to Date (`mtd`):** 1st of the current month to today (e.g. `1st to 26th October` vs `1st to 26th September`).
  2. **Last 30 days (`last_30_days`):** Rolling 30-day window to today vs immediately preceding 30 days.
  3. **Last 60 days (`last_60_days`):** Rolling 60-day window to today vs immediately preceding 60 days.
  4. **Last 90 days (`last_90_days`):** Rolling 90-day window to today vs immediately preceding 90 days.
  5. **Current Financial Year (`current_fy`):** Indian fiscal year starting 1st April to today (e.g. `FY 2026-27`) vs same period in prior fiscal year.
  6. **Previous Financial Year (`previous_fy`):** Preceding full fiscal year (1st April to 31st March, e.g. `FY 2025-26`) vs fiscal year before that.
  7. **Custom date range (`custom`):** Interactive date picker with `From` and `To` date inputs and an **Apply** button, computing exact period deltas on demand.

### 8.3 Single-Thread 'Ask O3' Conversational AI (Ollama)

The assistant ("Ask O3") provides concise, natural-language executive answers directly from Tally ERP figures:
- **Single Ongoing Conversation Thread:** Exactly one continuous conversation stream per user and company, persisted in the `chat_messages` table.
- **Local Ollama Integration:** Connects to Ollama (configured via `ollama_host` and `ollama_model` in `backend_config.json` or `OLLAMA_HOST` and `OLLAMA_MODEL` environment variables, defaulting to `http://localhost:11434` and `qwen2.5:7b`).
- **Completely Optional with Deterministic Fallback:** Ollama is not required to launch or use the app. If Ollama is offline or not installed, the assistant automatically routes queries to deterministic Python analytics functions with a 3.0s timeout.
- **Deterministic Python Tools & Rule-Based Fallback:**
  - Wraps `AnalyticsService` in deterministic Python functions (`get_collections_summary`, `get_sales_summary`, `get_receivables_summary`, `get_purchases_summary`, `get_slowest_paying_customers_summary`, `get_unpaid_invoices_summary`).
  - Includes an autonomous fallback router so questions like `"How were collections this month?"`, `"Who pays me the slowest?"`, and `"Which invoices are unpaid?"` return instant accurate financial answers even before Ollama is started or during model downloads.
- **Weighted Days Sales Outstanding (DSO) Calculation:** Pairs `new` and `agst` bill events to compute customer payment delays vs company benchmarks (e.g., `"Vardhman Packaging - 47 days over the last 12 months, vs your 34-day average."`).
- **Pre-Configured Try Asking Chips:** One-click prompt chips for immediate executive queries.

### 8.4 Argon2id Authentication & Multi-Tenant User Management

- **Password Hashing:** State-of-the-art Argon2id one-way salted hashing via `argon2-cffi`.
- **JWT Session Tokens:** Signed HMAC-SHA256 tokens (`pyjwt`) with 24-hour expiration for secure API requests.
- **Multi-Tenant User Isolation:** Each user belongs to an organization client and can access one or more assigned company GUIDs (`user_companies`).

### 8.5 Launching the Dashboard

1. **Start the API Server:**
   ```powershell
   Set-Location "E:\Tally\Tally Backend ETL v1.0"
   $env:PYTHONPATH="src"
   py -m uvicorn backend_ETL.api:create_app --factory --host 0.0.0.0 --port 8000 --reload
   ```
2. **Access in Browser:**
   - Sign In / Register: `http://localhost:8000/login`
   - Executive Dashboard: `http://localhost:8000/dashboard`

---

## 9. REST API Reference

For detailed payload schemas, request headers, error codes, and curl examples, see:
👉 [**Replication API Specification & Client Implementation Guide**](replication_api_usage_guide.md)

### 9.1 Replication Ingestion Endpoints:
- `POST /api/v1/clients` — Onboard client
- `POST /api/v1/companies` — Register company mapping
- `POST /api/v1/masters/batch` — Bulk upsert masters (ledgers, groups, items, godowns)
- `POST /api/v1/vouchers/batch` — Bulk upsert vouchers with ledger and inventory legs
- `GET  /api/v1/watermarks` — Fetch high watermarks (`alter_id`) for incremental sync
- `POST /api/v1/canonical/transform` — Trigger on-demand Silver layer transformation

### 9.2 Authentication & User Endpoints:
- `POST /api/v1/auth/register` — Register organization client and owner user account
- `POST /api/v1/auth/login` — Authenticate user and receive signed JWT access token
- `GET  /api/v1/auth/me` — Retrieve authenticated user profile and company permissions

### 9.3 Analytics & Executive KPI Endpoints:
- `GET  /api/v1/analytics/overview` — Fetch 4 KPIs (Sales, Collections, Receivables, Purchases) with period deltas.
  - Query parameters:
    - `period`: `mtd` (default), `last_30_days`, `last_60_days`, `last_90_days`, `current_fy`, `previous_fy`, `custom`
    - `start_date`: Custom start date (`YYYY-MM-DD` or `DD-MM-YYYY`)
    - `end_date`: Custom end date (`YYYY-MM-DD` or `DD-MM-YYYY`)
    - `reference_date`: Optional anchor date to simulate a specific login date
- `GET  /api/v1/analytics/sync-status` — Books update status label (e.g. `"Books updated to 26 Oct"`)
- `GET  /api/v1/analytics/aging` — Slowest paying customers and DSO benchmark
- `GET  /api/v1/analytics/unpaid` — Overdue and unpaid customer invoices

### 9.4 Ask O3 Conversational Agent Endpoints:
- `GET    /api/v1/agent/messages` — Retrieve single-thread chat history for user and company
- `POST   /api/v1/agent/chat` — Submit query to Ask O3 assistant
- `DELETE /api/v1/agent/messages` — Clear single-thread conversation history

---

## 10. Logging & Production Deployment

### 10.1 Logging Architecture

- Logs rotate automatically at **10 MB** with **5 backups** retained (50 MB cap).
- Default Linux path: `/var/log/backend_etl/backend_etl.log`
- Default Windows path: `%ProgramData%\TallyBackendETL\logs\backend_etl.log`
- Configurable via `BACKEND_LOG_DIR` or `--log-dir`.

### 10.2 Linux Systemd Service Setup

Create `/etc/systemd/system/tally-backend-etl.service`:

```ini
[Unit]
Description=Tally Backend ETL FastAPI Service
After=network.target postgresql.service

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/app
ExecStart=/home/ec2-user/app/venv/bin/backend-etl --config /home/ec2-user/app/backend_config.json
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable tally-backend-etl
sudo systemctl start tally-backend-etl
sudo systemctl status tally-backend-etl
```

---

## 11. Testing & Verification

Database tests run against a **throwaway PostgreSQL database**. Set `TEST_DATABASE_URL`; those tests are skipped when it is not set. The test fixture **drops and recreates every model table** in that database, and refuses to run unless the database name contains `test`.

```bash
# Example throwaway database:
docker run -d --name tally-test-pg -e POSTGRES_PASSWORD=test -e POSTGRES_DB=tally_test -p 5544:5432 postgres:16
```

```powershell
$env:TEST_DATABASE_URL = "postgresql://postgres:test@localhost:5544/tally_test"
# Agent tests first try an Ollama server (25s timeout per call); point it at a closed port to skip that wait:
$env:OLLAMA_HOST = "http://127.0.0.1:9"
```

Run the test suite using pytest:

```bash
# Run all backend tests:
py -m pytest tests/

# Run targeted test suites:
py -m pytest tests/test_api_endpoints.py -v
py -m pytest tests/test_bronze_crud.py tests/test_bronze_api.py -v
py -m pytest tests/test_canonical_runner.py -v
py -m pytest tests/test_analytics_service.py -v
py -m pytest tests/test_agent_service.py -v
py -m pytest tests/unit/test_security.py -v
py -m pytest tests/unit/test_backend_etl.py -v
py -m pytest tests/test_schema_snapshot.py -v        # no database needed
py -m pytest tests/test_canonical_transformer.py -v
py -m pytest tests/test_date_utils.py -v
py -m pytest tests/test_formatters.py -v
```

---

*Tally Backend ETL Service v1.0.0 — Python 3.12+ — PostgreSQL 14+*
