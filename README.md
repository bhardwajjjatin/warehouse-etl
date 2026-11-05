# Warehouse ETL

A configurable Python ETL example combining CSV, Excel, SQL databases, Google Sheets and SFTP deliveries into a SQLite warehouse. A fictional kit lending library supplies eight checkouts across four kits, totaling 32 loan days.

## Run the combined demo

Use Python 3.10 or later from the repository root.

```sh
python -m pip install -r requirements.txt
python prepare_demo.py
python run.py --config config/demo.json
```

Preparation creates a synthetic SQLite source. The pipeline creates `build/lending.sqlite` and prints monthly loan counts and loan days.

| Input | Demo records | Implementation |
| --- | --- | --- |
| CSV | T001–T002 | Local file with a header |
| Excel | T003–T004 | XLSX sheet and configured cell range |
| SQL database | T005–T006 | SQLAlchemy connection and an extraction SQL file |
| Google Sheets | T007 | Local JSON fixture matching the Sheets values response |
| SFTP delivery | T008 | Local inbox CSV fixture |

The Google Sheets and SFTP demo entries run offline. Live adapters are available through the service configuration. Every sample file contains fictional records. The workbook has a single Checkouts sheet with two records, typed dates and numeric durations.

## Configure sources

`config/demo.json` lists sources to combine. Paths resolve relative to the configuration. Each source returns six fields in this order.

```text
ticket_code,kit_code,kit_label,kit_family,loan_day,days_out
```

Use distinct ticket codes across sources. Excel dates can be native date cells. Text dates use ISO YYYY-MM-DD. Durations must be positive whole numbers. Sheets rows with omitted trailing cells are padded and validated.

Copy `config/services.example.json` to `config/services.local.json`, edit the source entries you need and set their named environment variables.

```sh
python run.py --config config/services.local.json
```

| Connector | Settings |
| --- | --- |
| SQL | SOURCE_DATABASE_URL supplies a SQLAlchemy URL. Install the matching driver for SQL Server, MySQL or another engine. The demo uses SQLite. Customize the extraction SQL to select and alias the six contract fields. Use a read-only account. |
| Google Sheets | SHEETS_DOCUMENT_ID identifies a spreadsheet shared with the service account. GOOGLE_APPLICATION_CREDENTIALS points to its JSON key file. The adapter requests the configured range with read-only scope. |
| SFTP | SFTP_HOST, SFTP_USER, SFTP_KEY_PATH and SFTP_KNOWN_HOSTS configure key authentication and trusted host keys. Download an explicit remote_path, or set latest to true to choose the latest CSV/XLSX in a folder by modification time. XLSX deliveries use the Checkouts sheet. |

SFTP retrieval keeps remote files in place. Store keys and service account files outside the repository. Git ignores local configurations, environment files, secrets directories, generated databases and build files.

The smaller CSV entry point is also available.

```sh
python run.py
python run.py --source example.csv --database build/example.sqlite
```

## Load into SQL Server

Install Microsoft ODBC Driver 18 for SQL Server on the machine running the pipeline, then install the Python dependencies.

```sh
python -m pip install -r requirements-sqlserver.txt
```

Set DESTINATION_DATABASE_URL to a SQLAlchemy SQL Server URL. For Windows integrated authentication in PowerShell, use your own server and an existing dedicated warehouse database.

```powershell
$env:DESTINATION_DATABASE_URL = 'mssql+pyodbc://@localhost/kit_warehouse?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes'
python run.py --config config/services.local.json --destination-url-env DESTINATION_DATABASE_URL
```

For the synthetic local sources, run prepare_demo.py and use config/demo.json instead. SQL authentication can also be supplied through an environment variable using a correctly URL-encoded SQLAlchemy connection URL.

The destination writer in destinations.py creates dbo.checkout_stage, dbo.kit_catalog and dbo.kit_loan in the selected database and replaces their rows on each successful refresh. It creates dbo.monthly_lending using sql/sqlserver_report.sql and runs sql/sqlserver_refresh.sql for the transformations. Use a dedicated database because those table names are owned by this example.

The database must already exist. The destination account needs table and view creation/alteration, data read/write permissions and permission to acquire an application lock. SQL Server 2016 SP1 or later supports the report's CREATE OR ALTER VIEW statement. The writer serializes refreshes with a transaction-owned application lock and rolls back failed snapshots. Source and destination connection URLs can point to different servers.

The SQL Server writer has mocked transaction and SQL compilation tests. Live execution requires an available SQL Server, ODBC driver and your connection settings.

## Transform and report

Adapters extract records and shared validation checks their fields. The combined snapshot enters checkout_stage. The transformations in sql/refresh.sql build kit_catalog and kit_loan, linked by a foreign key. The monthly_lending view aggregates by checkout month and kit family.

```sql
SELECT loan_month, kit_family, loan_count, loan_days
FROM monthly_lending
ORDER BY loan_month, kit_family;
```

April's two Astronomy loans total ten loan days. A loan contributes its full duration to its checkout month. Every successful run replaces the complete snapshot in one transaction. Duplicate tickets, conflicting kit descriptions, invalid records and extraction failures roll back the refresh. Sources are extracted sequentially, so their snapshots reflect their individual extraction times.

## Verify

```sh
python -m unittest discover -s tests -v
```

Tests exercise real local CSV, XLSX and SQLite extraction, combined reporting, repeated loads, snapshot replacement and rollback. Google Sheets requests and SFTP downloads use mocked clients, including latest-file selection, CSV/XLSX parsing and host-key policy. Live service access requires your own configuration and credentials.
