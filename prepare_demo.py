"""Build the synthetic SQLite source used by config/demo.json."""
import csv
import sqlite3
from contextlib import closing

from run import ROOT
from sources import FIELDS


def prepare():
    destination = ROOT / "build" / "source.sqlite"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with (ROOT / "data" / "demo" / "database-seed.csv").open(newline="", encoding="utf-8") as stream:
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
