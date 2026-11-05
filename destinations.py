"""Publish a validated snapshot to SQL Server through SQLAlchemy."""

from pathlib import Path


def refresh_sql_server(rows, url):
    from sqlalchemy import (
        CheckConstraint, Column, ForeignKey, Integer, MetaData, Table,
        Unicode, create_engine, text,
    )

    engine = create_engine(url, hide_parameters=True)
    try:
        if engine.dialect.name != "mssql":
            raise ValueError("the destination URL must use a SQL Server dialect")
        metadata = MetaData(schema="dbo")
        stage = Table(
            "checkout_stage", metadata,
            Column("ticket_code", Unicode(160), primary_key=True),
            Column("kit_code", Unicode(160), nullable=False),
            Column("kit_label", Unicode(250), nullable=False),
            Column("kit_family", Unicode(160), nullable=False),
            Column("loan_day", Unicode(10), nullable=False),
            Column("days_out", Integer, nullable=False),
            CheckConstraint("days_out > 0"),
        )
        Table(
            "kit_catalog", metadata,
            Column("kit_code", Unicode(160), primary_key=True),
            Column("kit_label", Unicode(250), nullable=False),
            Column("kit_family", Unicode(160), nullable=False),
        )
        Table(
            "kit_loan", metadata,
            Column("ticket_code", Unicode(160), primary_key=True),
            Column("kit_code", Unicode(160), ForeignKey("dbo.kit_catalog.kit_code"), nullable=False),
            Column("loan_day", Unicode(10), nullable=False),
            Column("days_out", Integer, nullable=False),
            CheckConstraint("days_out > 0"),
        )
        root = Path(__file__).resolve().parent
        with engine.begin() as connection:
            # Serialize refreshes, including first-time table creation.
            connection.execute(text("""
                DECLARE @result int;
                EXEC @result = sys.sp_getapplock
                    @Resource = 'pocket_warehouse_refresh',
                    @LockMode = 'Exclusive', @LockOwner = 'Transaction',
                    @LockTimeout = 60000;
                IF @result < 0 THROW 50000, 'Warehouse refresh lock unavailable', 1;
            """))
            metadata.create_all(connection)
            connection.execute(stage.delete())
            fields = list(stage.columns.keys())
            for row in rows:
                record = dict(zip(fields, row))
                for column in stage.columns:
                    limit = getattr(column.type, "length", None)
                    if limit and len(record[column.name]) > limit:
                        raise ValueError(f"{column.name} exceeds {limit} characters")
                connection.execute(stage.insert(), record)
            for statement in (root / "sql" / "sqlserver_refresh.sql").read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    connection.execute(text(statement))
            # SQL Server requires CREATE VIEW to be the first statement in a batch.
            connection.execute(text((root / "sql" / "sqlserver_report.sql").read_text(encoding="utf-8")))
            return connection.execute(text(
                "SELECT loan_month, kit_family, loan_count, loan_days "
                "FROM dbo.monthly_lending ORDER BY loan_month, kit_family"
            )).fetchall()
    finally:
        engine.dispose()
