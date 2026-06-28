# Redshift Migration

This document describes how the existing PostgreSQL-based feature store and data
pipeline would be migrated to Amazon Redshift for a production deployment. It
covers the rationale, the concrete SQL changes required, the S3-to-Redshift
loading pattern, dbt adapter compatibility, and the components that remain
unchanged.

The current stack persists through SQLAlchemy against SQLite locally and
PostgreSQL on Render. The dbt models under `dbt_models/` (`staging/stg_payments.sql`
and `marts/mart_merchant_payment_performance.sql`) build the analytical feature
layer on top of that store. The notes below are written against that layout.

## Why Redshift

- **Columnar storage suits the payment analytics query pattern.** The workload is
  dominated by aggregations over large transaction volumes — success rates by
  merchant, failure-risk cohorts, balance-band analysis, time-windowed recovery
  metrics. Redshift's columnar layout reads only the columns a query touches and
  compresses each column independently, so wide scan-and-aggregate queries over
  millions of payments are far cheaper than the row-oriented full scans
  PostgreSQL performs for the same analytics.
- **Managed scaling removes the operational overhead of PostgreSQL on EC2.**
  Running PostgreSQL ourselves means sizing instances, managing storage growth,
  tuning vacuum/autovacuum, and handling backups, failover, and version
  upgrades. Redshift (or Redshift Serverless) handles provisioning, elastic
  resize, automated snapshots, and patching, letting the team scale compute for
  analytics independently of the transactional write path.
- **Redshift Spectrum allows querying S3-stored raw data without loading it.**
  Raw payment files landed in S3 can be queried in place through external
  Spectrum tables, so cold or high-volume history does not have to be loaded
  into managed Redshift storage to be joined against the warehouse. This keeps
  storage costs down and lets the warehouse hold only the curated, frequently
  queried feature tables.

## SQL Changes Required

The DDL that backs the feature store and the operational/audit tables must be
adapted to Redshift's dialect. The key differences:

- **`SERIAL` → `BIGINT IDENTITY(1,1)`.** Redshift does not support the `SERIAL`
  pseudo-type. Auto-incrementing surrogate keys are declared as
  `BIGINT IDENTITY(1,1)`. Note that Redshift IDENTITY values are monotonic but
  not guaranteed gap-free, which is acceptable for surrogate keys.
- **`gen_random_uuid()` → Python-side UUID generation.** Redshift has limited
  native UUID support and no `pgcrypto` `gen_random_uuid()`. Generate UUIDs in
  the application layer (Python `uuid.uuid4()`) and insert them as
  `VARCHAR(36)` / `CHAR(36)` values. This also keeps idempotency keys and trace
  IDs consistent regardless of which engine is behind SQLAlchemy.
- **`jsonb` → `VARCHAR(max)` + application-layer parsing.** Redshift has no
  `jsonb` type. Store serialized JSON in a `VARCHAR(MAX)` column and parse it in
  the application (or use Redshift's `JSON_PARSE`/`SUPER` only where strictly
  needed). For the audit and span payloads this means serializing on write and
  deserializing on read in Python rather than relying on in-database JSON
  operators.
- **`TIMESTAMPTZ` → `TIMESTAMP`.** Redshift's `TIMESTAMP` is timezone-naive and
  conventionally stores UTC. Persist all timestamps in UTC and move timezone
  conversion and presentation into the application layer (the dashboard and API
  already work in terms of explicit instants, so this is a normalization on
  write rather than a behavioral change).
- **`CREATE INDEX` → `SORTKEY` / `DISTKEY` declarations.** Redshift does not have
  secondary B-tree indexes; physical query performance is governed by the sort
  key and distribution key chosen at table creation. Good candidates here:
  - **`created_at` (or `payment_date`) as `SORTKEY`.** Most analytics are
    time-bounded — monthly success rates, recovery windows, recent high-risk
    payments. A sort key on the event timestamp lets Redshift's zone maps skip
    blocks outside the requested range, turning time-range filters into
    near-index-like scans.
    `merchant_id` as a compound or interleaved sort key may help merchant-scoped
    time queries.
  - **`merchant_id` as `DISTKEY`.** Merchant-level aggregations and merchant-to-
    payment joins (e.g. `mart_merchant_payment_performance`) benefit from
    co-locating all rows for a merchant on the same compute slice, eliminating
    cross-node data shuffles during `GROUP BY merchant_id` and merchant joins.
  - Small, frequently joined dimension tables can use `DISTSTYLE ALL` so they
    are replicated to every slice instead of distributed.

## Loading Pattern

The pipeline shifts from direct database writes to an S3-staged batch load:

1. **Raw data lands in S3.** The data pipeline (`src/data_pipeline.py`) or
   upstream systems write raw payment records to an S3 prefix
   (e.g. partitioned `s3://.../raw/payments/dt=YYYY-MM-DD/`), in a
   COPY-friendly format such as Parquet, gzipped CSV, or JSON.
2. **`COPY` loads S3 into staging tables.** Redshift's `COPY` command bulk-loads
   from S3 into staging tables in parallel across slices — the canonical
   high-throughput ingestion path — using an IAM role for S3 access and the
   appropriate `FORMAT AS PARQUET` / `CSV` / region options. Loading into
   dedicated staging tables keeps raw ingestion separate from the curated
   layer.
3. **dbt models build the feature store.** The existing dbt models under
   `dbt_models/` run their transformations on top of the staging tables and
   produce the curated staging and mart layers
   (`stg_payments` → `mart_merchant_payment_performance`). Because the models
   use standard SQL, they require minimal changes to run against the loaded
   staging data.

## dbt Compatibility

- **Adapter / profile change.** The existing `dbt_models/` directory targets
  SQLite/PostgreSQL. Switching to Redshift requires installing the
  `dbt-redshift` adapter and updating `profiles.yml` to point at the Redshift
  cluster (host, port `5439`, database, schema, and credentials or IAM-based
  auth). Model `materialized` strategies (`view`/`table`) carry over; large
  marts may additionally specify Redshift-specific `sort` and `dist` configs.
- **Model SQL is portable.** All model SQL uses standard `SELECT` / `JOIN` /
  window functions and contains no SQLite-specific syntax, so `stg_payments.sql`
  and `mart_merchant_payment_performance.sql` are compatible with Redshift as
  written. The main review items are functions that differ subtly across engines
  (date arithmetic, string functions); the current models stay within the common
  SQL surface that Redshift supports.

## What Stays the Same

- **Feature engineering logic is database-agnostic.** `src/feature_store.py`
  computes features over data accessed through SQLAlchemy and pandas, so it does
  not depend on the underlying engine — it runs unchanged against Redshift.
- **MLflow tracking is independent of the database.** Model training, parameters,
  metrics, and artifacts are tracked through MLflow's own store and are
  unaffected by the warehouse migration.
- **The Streamlit dashboard only needs a new connection string.** The dashboard
  queries through SQLAlchemy; pointing it at Redshift (via the
  `redshift+psycopg2` / `redshift_connector` dialect) is a connection-string and
  driver change, not a query-logic change.
