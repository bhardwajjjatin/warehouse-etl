"""Refresh a lending warehouse from files, SQL, Google Sheets or SFTP."""

import argparse
import csv
import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
from sources import FIELDS, configured_rows, csv_rows, required_env

ROOT = Path(__file__).resolve().parent


def read_checkouts(source):
    """Yield validated rows and identify malformed records by line number."""
    records = csv_rows(source) if isinstance(source, Path) else source
    for number, row in enumerate(records, start=2):
        values = [str(row.get(name) if row.get(name) is not None else "").strip() for name in FIELDS]
        if not all(values):
            raise ValueError(f"record {number}: expected six nonempty fields")
        ticket, kit, label, family, day, duration = values
        raw_day = row.get("loan_day")
        if isinstance(raw_day, datetime):
            day = raw_day.date().isoformat()
        elif isinstance(raw_day, date):
            day = raw_day.isoformat()
        try:
            canonical_day = date.fromisoformat(day).isoformat()
            days_out = int(duration)
            if day != canonical_day or not 1 <= days_out <= 2147483647:
                raise ValueError
        except ValueError as error:
            raise ValueError(f"record {number}: invalid loan_day or days_out") from error
        yield ticket, kit, label, family, canonical_day, days_out


def refresh(source, database):
    """Replace one complete snapshot and return its monthly summary."""
    schema = (ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
    transforms = (ROOT / "sql" / "refresh.sql").read_text(encoding="utf-8")
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database, isolation_level=None)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        # Keep schema creation, staging and publishing in a single transaction.
        with connection:
            connection.executescript("BEGIN IMMEDIATE;\n" + schema)
            connection.execute("DELETE FROM checkout_stage")
            connection.executemany(
                "INSERT INTO checkout_stage "
                "(ticket_code, kit_code, kit_label, kit_family, loan_day, days_out) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                read_checkouts(source),
            )
            # executescript can implicitly commit. Execute the individual load
            # statements to preserve the transaction opened above.
            statement = ""
            for line in transforms.splitlines(keepends=True):
                statement += line
                if sqlite3.complete_statement(statement):
                    connection.execute(statement)
                    statement = ""
            if statement.strip():
                raise ValueError("incomplete SQL statement in refresh script")
            return connection.execute(
                "SELECT loan_month, kit_family, loan_count, loan_days "
                "FROM monthly_lending ORDER BY loan_month, kit_family"
            ).fetchall()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--source", type=Path, default=ROOT / "data" / "checkouts.csv")
    inputs.add_argument("--config", type=Path, help="JSON configuration of sources to combine")
    targets = parser.add_mutually_exclusive_group()
    targets.add_argument("--database", type=Path, default=ROOT / "build" / "lending.sqlite")
    targets.add_argument("--destination-url-env", help="environment variable holding a SQL Server SQLAlchemy URL")
    args = parser.parse_args()
    try:
        source = configured_rows(args.config) if args.config else args.source
        if args.destination_url_env:
            from destinations import refresh_sql_server
            rows = refresh_sql_server(read_checkouts(source), required_env(args.destination_url_env))
        else:
            rows = refresh(source, args.database)
    except Exception:
        # Connector errors can contain service URLs or authentication details.
        # Keep public console output free of those details.
        parser.exit(1, "Refresh failed. Check source configuration, access and input records.\n")
    print("Month    Family           Loans  Loan days")
    for month, family, loans, days in rows:
        print(f"{month}  {family:<15}  {loans:>4}  {days:>9}")


if __name__ == "__main__":
    main()
