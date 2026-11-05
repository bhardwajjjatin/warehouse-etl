import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.dialects import mssql
from sqlalchemy.schema import CreateTable

from destinations import refresh_sql_server


class SqlServerTests(unittest.TestCase):
    def test_transaction_orders_tables_and_loads_validated_records(self):
        engine = MagicMock()
        engine.dialect.name = "mssql"
        connection = engine.begin.return_value.__enter__.return_value
        record = ("T100", "K10", "Sample Kit", "Music", "2025-01-01", 3)
        with patch("sqlalchemy.create_engine", return_value=engine):
            with patch("sqlalchemy.MetaData.create_all", autospec=True) as create:
                refresh_sql_server(iter([record]), "mssql+pyodbc://")
        metadata = create.call_args.args[0]
        self.assertEqual(set(metadata.tables), {"dbo.checkout_stage", "dbo.kit_catalog", "dbo.kit_loan"})
        ddl = str(CreateTable(metadata.tables["dbo.kit_loan"]).compile(dialect=mssql.dialect()))
        self.assertIn("FOREIGN KEY", ddl)
        self.assertIn("NVARCHAR(160)", ddl)
        calls = connection.execute.call_args_list
        self.assertIn("sp_getapplock", str(calls[0].args[0]))
        inserted = [call for call in calls if len(call.args) == 2]
        self.assertEqual(inserted[0].args[1]["ticket_code"], "T100")
        statements = [str(call.args[0]) for call in calls]
        self.assertTrue(any("CREATE OR ALTER VIEW" in sql for sql in statements))
        engine.begin.return_value.__exit__.assert_called_once_with(None, None, None)
        engine.dispose.assert_called_once()

    def test_extraction_failure_exits_transaction_with_error(self):
        def broken_rows():
            yield ("T100", "K10", "Sample Kit", "Music", "2025-01-01", 3)
            raise OSError("source unavailable")

        engine = MagicMock()
        engine.dialect.name = "mssql"
        engine.begin.return_value.__exit__.return_value = False
        with patch("sqlalchemy.create_engine", return_value=engine):
            with patch("sqlalchemy.MetaData.create_all"):
                with self.assertRaises(OSError):
                    refresh_sql_server(broken_rows(), "mssql+pyodbc://")
        self.assertIs(engine.begin.return_value.__exit__.call_args.args[0], OSError)
        engine.dispose.assert_called_once()

    def test_rejects_another_destination_dialect(self):
        engine = MagicMock()
        engine.dialect.name = "sqlite"
        with patch("sqlalchemy.create_engine", return_value=engine):
            with self.assertRaises(ValueError):
                refresh_sql_server([], "sqlite://")
        engine.begin.assert_not_called()
        engine.dispose.assert_called_once()
