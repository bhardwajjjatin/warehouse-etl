DELETE FROM {edw}.fact_kit_loan;
DELETE FROM {edw}.dim_kit;
DELETE FROM {edw}.dim_date;

INSERT INTO {edw}.dim_kit (kit_code, kit_label, kit_family)
SELECT DISTINCT kit_code, kit_label, kit_family
FROM {edw_raw}.checkout_snapshot;

INSERT INTO {edw}.dim_date
    (date_key, calendar_date, calendar_year, calendar_month, calendar_day)
SELECT DISTINCT
    CAST(CONVERT(char(8), loan_day, 112) AS int),
    loan_day, YEAR(loan_day), MONTH(loan_day), DAY(loan_day)
FROM {edw_raw}.checkout_snapshot;

INSERT INTO {edw}.fact_kit_loan (ticket_code, kit_key, loan_date_key, days_out)
SELECT snapshot.ticket_code, kit.kit_key, calendar.date_key, snapshot.days_out
FROM {edw_raw}.checkout_snapshot AS snapshot
JOIN {edw}.dim_kit AS kit ON kit.kit_code = snapshot.kit_code
JOIN {edw}.dim_date AS calendar ON calendar.calendar_date = snapshot.loan_day;
