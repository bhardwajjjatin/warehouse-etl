CREATE TABLE IF NOT EXISTS checkout_stage (
    ticket_code TEXT PRIMARY KEY NOT NULL,
    kit_code TEXT NOT NULL,
    kit_label TEXT NOT NULL,
    kit_family TEXT NOT NULL,
    loan_day TEXT NOT NULL,
    days_out INTEGER NOT NULL CHECK (days_out > 0)
);

CREATE TABLE IF NOT EXISTS kit_catalog (
    kit_code TEXT PRIMARY KEY NOT NULL,
    kit_label TEXT NOT NULL,
    kit_family TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kit_loan (
    ticket_code TEXT PRIMARY KEY NOT NULL,
    kit_code TEXT NOT NULL REFERENCES kit_catalog (kit_code),
    loan_day TEXT NOT NULL,
    days_out INTEGER NOT NULL CHECK (days_out > 0)
);

CREATE VIEW IF NOT EXISTS monthly_lending AS
SELECT
    substr(loan.loan_day, 1, 7) AS loan_month,
    kit.kit_family,
    count(*) AS loan_count,
    sum(loan.days_out) AS loan_days
FROM kit_loan AS loan
JOIN kit_catalog AS kit ON kit.kit_code = loan.kit_code
GROUP BY substr(loan.loan_day, 1, 7), kit.kit_family;
