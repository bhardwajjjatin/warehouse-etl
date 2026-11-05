import csv
import io
import json
import sqlite3
import stat
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from prepare_demo import prepare
from run import ROOT, refresh
from sources import FIELDS, configured_rows, google_rows, sftp_rows


class SourceTests(unittest.TestCase):
    def test_combined_demo_matches_complete_snapshot(self):
        prepare()
        with TemporaryDirectory() as folder:
            combined = refresh(configured_rows(ROOT / "config/demo.json"), Path(folder) / "combined.sqlite")
            expected = refresh(ROOT / "data/checkouts.csv", Path(folder) / "expected.sqlite")
            self.assertEqual(combined, expected)
            self.assertEqual(sum(row[2] for row in combined), 8)

    def test_failure_in_later_source_preserves_previous_snapshot(self):
        with TemporaryDirectory() as folder:
            database = Path(folder) / "warehouse.sqlite"
            expected = refresh(ROOT / "data/checkouts.csv", database)
            config = Path(folder) / "broken.json"
            config.write_text(json.dumps({"sources": [
                {"type": "csv", "path": str(ROOT / "data/demo/desk.csv")},
                {"type": "excel", "path": "missing.xlsx"}
            ]}))
            with self.assertRaises(FileNotFoundError):
                refresh(configured_rows(config), database)
            with closing(sqlite3.connect(database)) as connection:
                actual = connection.execute(
                    "SELECT * FROM monthly_lending ORDER BY loan_month, kit_family"
                ).fetchall()
            self.assertEqual(actual, expected)

    def test_google_request_and_short_rows(self):
        with patch("google.oauth2.service_account.Credentials.from_service_account_file") as credentials:
            with patch("googleapiclient.discovery.build") as build:
                service = build.return_value.__enter__.return_value
                request = service.spreadsheets.return_value.values.return_value.get
                request.return_value.execute.return_value = {"values": [list(FIELDS), ["T100"]]}
                records = list(google_rows("demo-document", "Checkouts!A1:F10", "demo-key.json"))
                request.assert_called_once_with(spreadsheetId="demo-document", range="Checkouts!A1:F10")
                self.assertEqual(records[0]["ticket_code"], "T100")
                self.assertIsNone(records[0]["days_out"])
                self.assertEqual(credentials.call_args.kwargs["scopes"],
                                 ["https://www.googleapis.com/auth/spreadsheets.readonly"])

    def test_sftp_latest_csv_and_excel(self):
        csv_bytes = (ROOT / "data/demo/sftp-inbox/checkouts.csv").read_bytes()
        excel_bytes = (ROOT / "data/demo/workbook.xlsx").read_bytes()
        for extension, payload, expected_count in (("csv", csv_bytes, 1), ("xlsx", excel_bytes, 2)):
            with self.subTest(extension=extension), patch("paramiko.SSHClient") as client_type:
                client = client_type.return_value.__enter__.return_value
                transfer = client.open_sftp.return_value.__enter__.return_value
                transfer.listdir_attr.return_value = [
                    SimpleNamespace(filename="old.csv", st_mtime=1, st_mode=stat.S_IFREG),
                    SimpleNamespace(filename="latest." + extension, st_mtime=2, st_mode=stat.S_IFREG),
                    SimpleNamespace(filename="folder.csv", st_mtime=3, st_mode=stat.S_IFDIR),
                ]
                transfer.getfo.side_effect = lambda path, buffer: buffer.write(payload)
                rows = list(sftp_rows("demo.invalid", "demo", "demo.key", "/incoming", "known_hosts", latest=True))
                self.assertEqual(len(rows), expected_count)
                self.assertEqual(transfer.getfo.call_args.args[0], "/incoming/latest." + extension)
                client.load_host_keys.assert_called_once_with("known_hosts")
                self.assertEqual(type(client.set_missing_host_key_policy.call_args.args[0]).__name__, "RejectPolicy")
                transfer.remove.assert_not_called()
