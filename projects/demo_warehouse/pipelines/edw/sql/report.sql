CREATE OR ALTER VIEW dbo.monthly_lending AS
SELECT
    CONVERT(char(7), calendar.calendar_date, 126) AS loan_month,
    kit.kit_family,
    COUNT_BIG(*) AS loan_count,
    SUM(CAST(loan.days_out AS bigint)) AS loan_days
FROM dbo.fact_kit_loan AS loan
JOIN dbo.dim_kit AS kit ON kit.kit_key = loan.kit_key
JOIN dbo.dim_date AS calendar ON calendar.date_key = loan.loan_date_key
GROUP BY CONVERT(char(7), calendar.calendar_date, 126), kit.kit_family;
