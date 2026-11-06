# Warehouse ETL

A generic ETL project organized around shared pipeline and utility modules, with project-specific staging, edw_raw and edw pipelines. CSV, Excel, SQL databases, Google Sheets and SFTP feed a fictional kit lending warehouse. The sample contains eight checkouts, four kits and 32 loan days.

## Folder structure

```text
warehouse-etl/
├── pipelines/
│   ├── __init__.py
│   ├── base.py
│   └── tests/
├── projects/
│   └── demo_warehouse/
│       ├── config.yaml
│       ├── data/
│       │   ├── checkouts.csv
│       │   └── demo/
│       └── pipelines/
│           ├── staging/
│           │   ├── config.yaml
│           │   ├── sources.demo.json
│           │   ├── sources.services.example.json
│           │   ├── py/
│           │   │   ├── prepare_demo.py
│           │   │   └── load_checkouts.py
│           │   ├── sql/
│           │   │   ├── create_databases.sql
│           │   │   ├── extract_checkouts.sql
│           │   │   └── sqlite_schema.sql
│           │   └── tests/
│           ├── edw_raw/
│           │   ├── config.yaml
│           │   ├── sql/load.sql
│           │   └── tests/
│           └── edw/
│               ├── config.yaml
│               ├── sql/
│               │   ├── clear_snapshot.sql
│               │   ├── load_dim_kit.sql
│               │   ├── load_dim_date.sql
│               │   ├── load_fact_kit_loan.sql
│               │   ├── report.sql
│               │   └── sqlite_load.sql
│               └── tests/
├── utils/
│   ├── __init__.py
│   ├── db.py
│   ├── sources.py
│   └── utils.py
├── run.py
├── requirements.txt
└── requirements-sqlserver.txt
```

Project config.yaml defines database names and pipeline order. Each pipeline config.yaml lists script sets and SQL quality checks. The shared runner executes sets and scripts sequentially, using the same SQL Server transaction. Python scripts expose main(connection, context, params). SQL scripts use the configured database names. Each quality query returns zero violations for a successful check.

## Run the local demo

Use Python 3.10 or later from the repository root.

```sh
python -m pip install -r requirements.txt
python run.py demo_warehouse all
```

This command prepares the fictional SQL source in build/source.sqlite and writes the local demo report to build/lending.sqlite. The local SQLite backend runs the complete snapshot.

| Input | Demo records | Extraction |
| --- | --- | --- |
| CSV | T001–T002 | Local header and values |
| Excel | T003–T004 | Checkouts sheet and configured range |
| SQL | T005–T006 | Synthetic SQLite source and extraction SQL |
| Google Sheets | T007 | JSON fixture matching a values response |
| SFTP | T008 | Local inbox CSV fixture |

Google Sheets and SFTP have live adapters in utils/sources.py. Their demo fixtures run offline. The workbook contains typed dates and numeric durations.

For a separate CSV snapshot:

```sh
python run.py demo_warehouse all --source projects/demo_warehouse/data/checkouts.csv --database build/example.sqlite
```

## Run SQL Server pipelines

Install Microsoft ODBC Driver 18 for SQL Server and the Python dependencies.

```sh
python -m pip install -r requirements-sqlserver.txt
```

Run projects/demo_warehouse/pipelines/staging/sql/create_databases.sql once as an administrator in SSMS. It creates staging, edw_raw and edw. Their names are configured in projects/demo_warehouse/config.yaml. If you use different names, adjust the creation script and configuration together.

All three databases must be on the same SQL Server instance. Configure the destination connection in an environment variable. For Windows integrated authentication in PowerShell:

```powershell
$env:DESTINATION_DATABASE_URL = 'mssql+pyodbc://@localhost/staging?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes'
python run.py demo_warehouse all --destination-url-env DESTINATION_DATABASE_URL
```

The destination account needs table and view creation/alteration, data read/write access across the three databases and permission to acquire an application lock in staging. SQL Server 2016 SP1 or later supports the reporting view definition.

Individual layers can also run against an existing warehouse snapshot.

```sh
python run.py demo_warehouse staging --destination-url-env DESTINATION_DATABASE_URL
python run.py demo_warehouse edw_raw --destination-url-env DESTINATION_DATABASE_URL
python run.py demo_warehouse edw --destination-url-env DESTINATION_DATABASE_URL
```

| Database | Tables | Role |
| --- | --- | --- |
| staging | dbo.checkout_stage | Combined validated source records |
| edw_raw | dbo.checkout_snapshot | Detailed records with SQL Server DATE values |
| edw | dbo.dim_kit, dbo.dim_date, dbo.fact_kit_loan | Star schema |
| edw | dbo.monthly_lending | Reporting view |

dim_kit uses an identity surrogate key and a unique business kit code. dim_date uses an integer YYYYMMDD key and calendar attributes. fact_kit_loan has one row per checkout ticket, references both dimensions and stores days_out. Date coverage follows the checkout dates in the source snapshot.

A successful run replaces the selected layers' complete snapshots. Dimension identity keys can change, and the fact load resolves them again. The staging application lock serializes refreshes. All selected SQL Server layers run in one transaction, and failures in extraction, transformation or SQL quality checks roll back the transaction. Separate layer invocations each have their own transaction.

## Connect live sources

Copy projects/demo_warehouse/pipelines/staging/sources.services.example.json to sources.services.local.json in the same directory and edit the entries you need. Source paths resolve relative to that configuration file. Every source must supply these fields in order.

```text
ticket_code,kit_code,kit_label,kit_family,loan_day,days_out
```

| Connector | Environment settings |
| --- | --- |
| SQL | SOURCE_DATABASE_URL holds a SQLAlchemy URL. Install the database driver for your source engine and use a read-only account. The extraction SQL selects and aliases the six fields. |
| Google Sheets | SHEETS_DOCUMENT_ID identifies the spreadsheet shared with the service account. GOOGLE_APPLICATION_CREDENTIALS points to its JSON key file. The reader requests the configured range with read-only scope. |
| SFTP | SFTP_HOST, SFTP_USER, SFTP_KEY_PATH and SFTP_KNOWN_HOSTS configure key authentication and host verification. Download an explicit path or the latest CSV/XLSX file by modification time. XLSX deliveries use the Checkouts sheet. |

```sh
python run.py demo_warehouse all --config projects/demo_warehouse/pipelines/staging/sources.services.local.json --destination-url-env DESTINATION_DATABASE_URL
```

Use distinct ticket codes across sources. Text dates use YYYY-MM-DD and native Excel dates are accepted. Loan durations must be positive whole numbers. Conflicting kit descriptions and duplicate tickets fail the load. SFTP retrieval keeps remote files in place. Store credentials outside the repository. Git ignores local configuration files, environment files, secrets directories and generated build files.

## Verify

```sh
python -m unittest discover -s pipelines/tests -v
```

The suite covers local CSV, XLSX and SQLite extraction, shared validation, repeat loads, rollback, SQL Server database routing and schema compilation. Google Sheets, SFTP and SQL Server service connections use mocks. Live database and service execution requires your own connection settings and credentials.
