import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.dialects import mssql
from sqlalchemy.schema import CreateTable

from utils.db import refresh_sql_server


class SqlServerTests(unittest.TestCase):
    def test_transaction_orders_tables_and_loads_validated_records(self):
        engine = MagicMock()
        engine.dialect.name = "mssql"
        connection = engine.begin.return_value.__enter__.return_value
        connection.execute.return_value.scalar.return_value = 0
        record = ("T100", "K10", "Sample Kit", "Music", "2025-01-01", 3)
        with patch("utils.db.create_engine", return_value=engine):
            with patch("sqlalchemy.MetaData.create_all", autospec=True) as create:
                refresh_sql_server(iter([record]), "mssql+pyodbc://")
        metadata = create.call_args.args[0]
        self.assertEqual(set(metadata.tables), {
            "dbo.checkout_stage", "dbo.checkout_snapshot",
            "dbo.dim_kit", "dbo.dim_date", "dbo.fact_kit_loan",
        })
        self.assertEqual(
            [[table.name for table in call.kwargs["tables"]] for call in create.call_args_list],
            [["checkout_stage"], ["checkout_snapshot"], ["dim_kit", "dim_date", "fact_kit_loan"]],
        )
        ddl = str(CreateTable(metadata.tables["dbo.fact_kit_loan"]).compile(dialect=mssql.dialect()))
        self.assertIn("FOREIGN KEY", ddl)
        self.assertIn("NVARCHAR(160)", ddl)
        self.assertIn("REFERENCES dbo.dim_kit", ddl)
        self.assertIn("REFERENCES dbo.dim_date", ddl)
        date_ddl = str(CreateTable(metadata.tables["dbo.dim_date"]).compile(dialect=mssql.dialect()))
        self.assertIn("calendar_date DATE", date_ddl)
        calls = connection.execute.call_args_list
        self.assertIn("sp_getapplock", str(calls[0].args[0]))
        inserted = [call for call in calls if len(call.args) == 2]
        self.assertEqual(inserted[0].args[1]["ticket_code"], "T100")
        statements = [str(call.args[0]) for call in calls]
        self.assertEqual([sql for sql in statements if sql.startswith("USE ")],
                         ["USE [staging]", "USE [edw_raw]", "USE [edw]", "USE [staging]"])
        self.assertTrue(any("CREATE OR ALTER VIEW" in sql for sql in statements))
        raw_load = next(i for i, sql in enumerate(statements) if "INSERT INTO [edw_raw]" in sql)
        edw_load = next(i for i, sql in enumerate(statements) if "INSERT INTO [edw].dbo.dim_kit" in sql)
        self.assertLess(raw_load, edw_load)
        self.assertIn("FROM [staging].dbo.checkout_stage", statements[raw_load])
        self.assertTrue(any("EXEC [edw].sys.sp_executesql" in sql for sql in statements))
        self.assertIn("FROM [edw].dbo.monthly_lending", statements[-1])
        engine.begin.return_value.__exit__.assert_called_once_with(None, None, None)
        engine.dispose.assert_called_once()

    def test_invalid_or_shared_database_names_fail_before_connecting(self):
        for names in (
            {"staging": "staging"},
            {"staging": "shared", "edw_raw": "SHARED", "edw": "edw"},
            {"staging": "stage]; DROP DATABASE edw", "edw_raw": "raw", "edw": "edw"},
        ):
            with self.subTest(names=names), patch("utils.db.create_engine") as create:
                with self.assertRaises(ValueError):
                    refresh_sql_server([], "mssql+pyodbc://", names)
                create.assert_not_called()

    def test_extraction_failure_exits_transaction_with_error(self):
        def broken_rows():
            yield ("T100", "K10", "Sample Kit", "Music", "2025-01-01", 3)
            raise OSError("source unavailable")

        engine = MagicMock()
        engine.dialect.name = "mssql"
        engine.begin.return_value.__exit__.return_value = False
        with patch("utils.db.create_engine", return_value=engine):
            with patch("sqlalchemy.MetaData.create_all"):
                with self.assertRaises(OSError):
                    refresh_sql_server(broken_rows(), "mssql+pyodbc://")
        self.assertIs(engine.begin.return_value.__exit__.call_args.args[0], OSError)
        engine.dispose.assert_called_once()

    def test_rejects_another_destination_dialect(self):
        engine = MagicMock()
        engine.dialect.name = "sqlite"
        with patch("utils.db.create_engine", return_value=engine):
            with self.assertRaises(ValueError):
                refresh_sql_server([], "sqlite://")
        engine.begin.assert_not_called()
        engine.dispose.assert_called_once()

    def test_edw_can_run_without_extracting_sources(self):
        def unrequested_source():
            raise AssertionError("an EDW run must use the existing raw snapshot")
            yield

        engine = MagicMock()
        engine.dialect.name = "mssql"
        connection = engine.begin.return_value.__enter__.return_value
        connection.execute.return_value.scalar.return_value = 0
        with patch("utils.db.create_engine", return_value=engine):
            with patch("sqlalchemy.MetaData.create_all"):
                refresh_sql_server(unrequested_source(), "mssql+pyodbc://", pipeline="edw")
        statements = [str(call.args[0]) for call in connection.execute.call_args_list]
        self.assertTrue(any("INSERT INTO [edw].dbo.fact_kit_loan" in sql for sql in statements))
        self.assertFalse(any("INSERT INTO [edw_raw]" in sql for sql in statements))
        self.assertFalse(any("DELETE FROM dbo.checkout_stage" in sql for sql in statements))

    def test_quality_failure_aborts_the_transaction(self):
        engine = MagicMock()
        engine.dialect.name = "mssql"
        engine.begin.return_value.__exit__.return_value = False
        connection = engine.begin.return_value.__enter__.return_value
        connection.execute.return_value.scalar.return_value = 1
        with patch("utils.db.create_engine", return_value=engine):
            with patch("sqlalchemy.MetaData.create_all"):
                with self.assertRaisesRegex(ValueError, "quality check failed"):
                    refresh_sql_server([], "mssql+pyodbc://", pipeline="edw_raw")
        self.assertIs(engine.begin.return_value.__exit__.call_args.args[0], ValueError)
