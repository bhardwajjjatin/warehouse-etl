"""Extract checkout records from local files and configurable services."""

import csv
import io
import json
import os
import posixpath
import stat
from pathlib import Path


FIELDS = ("ticket_code", "kit_code", "kit_label", "kit_family", "loan_day", "days_out")


def tabular(rows):
    """Convert a header and rectangular values into named records."""
    iterator = iter(rows)
    header = next(iterator, [])
    if list(header) != list(FIELDS):
        raise ValueError("source header must match the checkout contract")
    for row in iterator:
        if len(row) > len(FIELDS):
            raise ValueError("source row has extra fields")
        yield dict(zip(FIELDS, list(row) + [None] * (len(FIELDS) - len(row))))


def csv_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        yield from tabular(csv.reader(stream, strict=True))


def excel_rows(path, sheet="Checkouts", cell_range="A1:F10000"):
    from openpyxl import load_workbook
    from openpyxl.utils.cell import range_boundaries

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        minimum_col, minimum_row, maximum_col, maximum_row = range_boundaries(cell_range)
        rows = workbook[sheet].iter_rows(
            min_row=minimum_row, max_row=maximum_row,
            min_col=minimum_col, max_col=maximum_col, values_only=True,
        )
        yield from tabular(row for row in rows if any(value is not None for value in row))
    finally:
        workbook.close()


def sql_rows(url, query):
    """Use a read-only database account for external SQL sources."""
    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            result = connection.execute(text(query))
            yield from tabular([list(result.keys()), *result.fetchall()])
    finally:
        engine.dispose()


def google_rows(spreadsheet_id, cell_range, credentials_path):
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials.from_service_account_file(
        credentials_path, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    with build("sheets", "v4", credentials=credentials, cache_discovery=False) as service:
        response = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=cell_range
        ).execute()
        yield from tabular(response.get("values", []))


def sftp_rows(host, username, key_path, remote_path, known_hosts, port=22, latest=False):
    """Fetch CSV or XLSX with host-key verification and key authentication."""
    import paramiko

    with paramiko.SSHClient() as client:
        client.load_host_keys(known_hosts)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        client.connect(host, port=port, username=username, key_filename=key_path,
                       timeout=20, auth_timeout=20, banner_timeout=20,
                       look_for_keys=False, allow_agent=False)
        with client.open_sftp() as transfer:
            transfer.get_channel().settimeout(30)
            if latest:
                files = [entry for entry in transfer.listdir_attr(remote_path)
                         if stat.S_ISREG(entry.st_mode)
                         and Path(entry.filename).suffix.lower() in (".csv", ".xlsx")]
                if not files:
                    raise ValueError("SFTP folder contains no CSV or XLSX files")
                newest = max(files, key=lambda entry: (entry.st_mtime, entry.filename))
                remote_path = posixpath.join(remote_path, newest.filename)
            buffer = io.BytesIO()
            transfer.getfo(remote_path, buffer)
            buffer.seek(0)
            if Path(remote_path).suffix.lower() == ".csv":
                yield from tabular(csv.reader(io.StringIO(buffer.getvalue().decode("utf-8-sig")), strict=True))
            elif Path(remote_path).suffix.lower() == ".xlsx":
                yield from excel_rows(buffer)
            else:
                raise ValueError("SFTP input must be CSV or XLSX")


def required_env(name):
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"set environment variable {name}")
    return value


def configured_rows(config_path):
    """Resolve local paths relative to the configuration, then extract in order."""
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    sources = config["sources"]
    if not sources:
        raise ValueError("configure at least one source")
    for source in sources:
        kind = source["type"]
        path = config_path.parent / source.get("path", "")
        if kind == "csv":
            yield from csv_rows(path)
        elif kind == "excel":
            yield from excel_rows(path, source.get("sheet", "Checkouts"), source.get("range", "A1:F10000"))
        elif kind == "sql":
            url = required_env(source["url_env"]) if "url_env" in source else "sqlite:///" + path.as_posix()
            query = (config_path.parent / source["query_file"]).read_text(encoding="utf-8")
            yield from sql_rows(url, query)
        elif kind == "google_sheets":
            yield from google_rows(required_env(source["id_env"]), source["range"],
                                   required_env(source["credentials_env"]))
        elif kind == "sftp":
            yield from sftp_rows(
                required_env(source["host_env"]), required_env(source["user_env"]),
                required_env(source["key_env"]), source["remote_path"],
                required_env(source["known_hosts_env"]), source.get("port", 22),
                source.get("latest", False),
            )
        elif kind == "sheets_fixture":
            response = json.loads(path.read_text(encoding="utf-8"))
            yield from tabular(response["values"])
        else:
            raise ValueError(f"unsupported source type {kind}")
