"""Build the synthetic SQL source for the demonstration project."""
import csv
import sqlite3
from contextlib import closing

from pipelines.base import ROOT, PROJECT
from utils.sources import FIELDS


def prepare(project=PROJECT):
    destination = ROOT / "build" / "source.sqlite"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with (project / "data" / "demo" / "database-seed.csv").open(newline="", encoding="utf-8") as stream:
        reader = csv.reader(stream)
        if next(reader) != list(FIELDS):
            raise ValueError("unexpected source seed header")
        rows = list(reader)
    with closing(sqlite3.connect(destination)) as connection:
        with connection:
            connection.execute("CREATE TABLE IF NOT EXISTS lending_export "
                               "(ticket_code TEXT PRIMARY KEY, kit_code TEXT, kit_label TEXT, "
                               "kit_family TEXT, loan_day TEXT, days_out INTEGER)")
            connection.execute("DELETE FROM lending_export")
            connection.executemany("INSERT INTO lending_export VALUES (?, ?, ?, ?, ?, ?)", rows)


if __name__ == "__main__":
    prepare()
    print("Created the synthetic SQL source in build/source.sqlite")


def main(connection, context, params):
    if context.get("prepare_demo", False):
        prepare(context.get("project", PROJECT))
