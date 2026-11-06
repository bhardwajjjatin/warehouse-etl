INSERT INTO {edw}.dim_date
    (date_key, calendar_date, calendar_year, calendar_month, calendar_day)
SELECT DISTINCT
    CAST(CONVERT(char(8), loan_day, 112) AS int),
    loan_day, YEAR(loan_day), MONTH(loan_day), DAY(loan_day)
FROM {edw_raw}.checkout_snapshot;
