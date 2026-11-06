"""Load validated source records into the staging table."""


def main(connection, context, params):
    from utils.db import load_rows
    load_rows(connection, context["stage"], context["rows"])
