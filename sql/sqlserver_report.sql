CREATE OR ALTER VIEW dbo.monthly_lending AS
SELECT
    SUBSTRING(loan.loan_day, 1, 7) AS loan_month,
    kit.kit_family,
    COUNT_BIG(*) AS loan_count,
    SUM(CAST(loan.days_out AS bigint)) AS loan_days
FROM dbo.kit_loan AS loan
JOIN dbo.kit_catalog AS kit ON kit.kit_code = loan.kit_code
GROUP BY SUBSTRING(loan.loan_day, 1, 7), kit.kit_family;
