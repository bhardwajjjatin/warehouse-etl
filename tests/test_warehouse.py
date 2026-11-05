import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from run import ROOT, refresh


class WarehouseTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.database = Path(temp.name) / "warehouse.sqlite"
        self.source = Path(temp.name) / "input.csv"
        self.fixture = (ROOT / "data" / "checkouts.csv").read_text(encoding="utf-8")
        self.source.write_text(self.fixture, encoding="utf-8")

    def snapshot(self):
        with closing(sqlite3.connect(self.database)) as connection:
            return {
                table: connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
                for table in ("checkout_stage", "kit_catalog", "kit_loan")
            }

    def test_repeat_refresh(self):
        summary = refresh(self.source, self.database)
        self.assertIn(("2025-04", "Astronomy", 2, 10), summary)
        self.assertEqual(sum(row[2] for row in summary), 8)
        self.assertEqual(sum(row[3] for row in summary), 32)
        initial = self.snapshot()
        self.assertEqual(len(initial["kit_catalog"]), 4)
        self.assertEqual(refresh(self.source, self.database), summary)
        self.assertEqual(self.snapshot(), initial)

    def test_smaller_snapshot_replaces_old_loans_and_kits(self):
        refresh(self.source, self.database)
        self.source.write_text("\n".join(self.fixture.splitlines()[:2]), encoding="utf-8")
        self.assertEqual(refresh(self.source, self.database), [("2025-04", "Astronomy", 1, 4)])
        self.assertEqual([len(rows) for rows in self.snapshot().values()], [1, 1, 1])

    def test_invalid_refresh_restores_every_table(self):
        refresh(self.source, self.database)
        initial = self.snapshot()
        bad_records = [
            ("T001,K01,Paper Planets,Astronomy,2025-06-01,3", sqlite3.IntegrityError),
            ("T009,K01,Different Kit,Astronomy,2025-06-01,3", sqlite3.IntegrityError),
            ("T009,K01,Paper Planets,Astronomy,2025-02-30,3", ValueError),
            ("T009,K01,Paper Planets,Astronomy,2025-06-01,0", ValueError),
        ]
        for record, error in bad_records:
            with self.subTest(record=record):
                self.source.write_text(self.fixture.rstrip() + "\n" + record, encoding="utf-8")
                with self.assertRaises(error):
                    refresh(self.source, self.database)
                self.assertEqual(self.snapshot(), initial)
