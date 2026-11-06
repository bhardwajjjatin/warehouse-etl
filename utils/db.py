"""Publish a validated snapshot to SQL Server through SQLAlchemy."""
from pathlib import Path
import re
from sqlalchemy import (
        CheckConstraint, Column, ForeignKey, Identity, Integer, MetaData, Table,
        Unicode, create_engine, text,
    )
from sqlalchemy.dialects.mssql import DATE

def load_rows(connection, stage, rows):
    fields = list(stage.columns.keys())
    for row in rows:
        record = dict(zip(fields, row))
        for column in stage.columns:
            limit = getattr(column.type, "length", None)
            if limit and len(record[column.name]) > limit:
                raise ValueError(f"{column.name} exceeds {limit} characters")
        connection.execute(stage.insert(), record)


def refresh_sql_server(rows, url, databases=None, project=None, pipeline="all", prepare_demo=False):
    from pipelines.base import run_pipeline
    from utils.utils import load_config
    project = Path(project) if project else Path(__file__).resolve().parents[1] / "projects/demo_warehouse"
    project_config = load_config(project / "config.yaml")
    selected = project_config["pipelines"]
    if pipeline != "all":
        selected = [item for item in selected if item["name"] == pipeline]
    if not selected:
        raise ValueError("unknown pipeline")

    if databases is None:
        databases = {"staging": "staging", "edw_raw": "edw_raw", "edw": "edw"}
    if set(databases) != {"staging", "edw_raw", "edw"}:
        raise ValueError("configure staging, edw_raw and edw database names")
    if any(not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", name)
           for name in databases.values()):
        raise ValueError("database names must be simple SQL identifiers")
    if len({name.casefold() for name in databases.values()}) != 3:
        raise ValueError("each warehouse layer needs a different database")
    engine = create_engine(url, hide_parameters=True)
    try:
        if engine.dialect.name != "mssql":
            raise ValueError("the destination URL must use a SQL Server dialect")
        metadata = MetaData()
        staging_schema = raw_schema = edw_schema = "dbo"
        stage = Table(
            "checkout_stage", metadata,
            Column("ticket_code", Unicode(160), primary_key=True),
            Column("kit_code", Unicode(160), nullable=False),
            Column("kit_label", Unicode(250), nullable=False),
            Column("kit_family", Unicode(160), nullable=False),
            Column("loan_day", Unicode(10), nullable=False),
            Column("days_out", Integer, nullable=False),
            CheckConstraint("days_out > 0"),
            schema=staging_schema,
        )
        raw = Table(
            "checkout_snapshot", metadata,
            Column("ticket_code", Unicode(160), primary_key=True),
            Column("kit_code", Unicode(160), nullable=False),
            Column("kit_label", Unicode(250), nullable=False),
            Column("kit_family", Unicode(160), nullable=False),
            Column("loan_day", DATE, nullable=False),
            Column("days_out", Integer, nullable=False),
            CheckConstraint("days_out > 0"),
            schema=raw_schema,
        )
        catalog = Table(
            "dim_kit", metadata,
            Column("kit_key", Integer, Identity(), primary_key=True),
            Column("kit_code", Unicode(160), nullable=False, unique=True),
            Column("kit_label", Unicode(250), nullable=False),
            Column("kit_family", Unicode(160), nullable=False),
            schema=edw_schema,
        )
        dates = Table(
            "dim_date", metadata,
            Column("date_key", Integer, primary_key=True, autoincrement=False),
            Column("calendar_date", DATE, nullable=False, unique=True),
            Column("calendar_year", Integer, nullable=False),
            Column("calendar_month", Integer, nullable=False),
            Column("calendar_day", Integer, nullable=False),
            schema=edw_schema,
        )
        loans = Table(
            "fact_kit_loan", metadata,
            Column("ticket_code", Unicode(160), primary_key=True),
            Column("kit_key", Integer, ForeignKey("dbo.dim_kit.kit_key"), nullable=False),
            Column("loan_date_key", Integer, ForeignKey("dbo.dim_date.date_key"), nullable=False),
            Column("days_out", Integer, nullable=False),
            CheckConstraint("days_out > 0"),
            schema=edw_schema,
        )
        with engine.begin() as connection:
            # Serialize refreshes, including first-time table creation.
            connection.execute(text(f"""
                DECLARE @result int;
                EXEC @result = [{databases["staging"]}].sys.sp_getapplock
                    @Resource = 'pocket_warehouse_refresh',
                    @LockMode = 'Exclusive', @LockOwner = 'Transaction',
                    @LockTimeout = 60000;
                IF @result < 0 THROW 50000, 'Warehouse refresh lock unavailable', 1;
            """))
            # Scope DDL to each database so foreign keys use local two-part names.
            for layer, tables in (("staging", [stage]), ("edw_raw", [raw]), ("edw", [catalog, dates, loans])):
                connection.execute(text(f"USE [{databases[layer]}]"))
                metadata.create_all(connection, tables=tables)
            connection.execute(text(f"USE [{databases['staging']}]"))
            parameters = {layer: "[" + name + "].dbo" for layer, name in databases.items()}
            context = {"stage": stage, "rows": rows, "databases": databases,
                       "prepare_demo": prepare_demo, "project": project}
            for layer in selected:
                if layer["name"] == "staging":
                    connection.execute(stage.delete())
                run_pipeline(connection, project / layer["dir"], context, parameters)
            if not any(layer["name"] == "edw" for layer in selected):
                return []
            return connection.execute(text(
                "SELECT loan_month, kit_family, loan_count, loan_days "
                f"FROM [{databases['edw']}].dbo.monthly_lending ORDER BY loan_month, kit_family"
            )).fetchall()
    finally:
        engine.dispose()
