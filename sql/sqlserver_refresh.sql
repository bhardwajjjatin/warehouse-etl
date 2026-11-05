DELETE FROM dbo.kit_loan;
DELETE FROM dbo.kit_catalog;

INSERT INTO dbo.kit_catalog (kit_code, kit_label, kit_family)
SELECT DISTINCT kit_code, kit_label, kit_family
FROM dbo.checkout_stage;

INSERT INTO dbo.kit_loan (ticket_code, kit_code, loan_day, days_out)
SELECT ticket_code, kit_code, loan_day, days_out
FROM dbo.checkout_stage;
