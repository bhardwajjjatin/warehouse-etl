DELETE FROM kit_loan;
DELETE FROM kit_catalog;

-- A kit code must describe exactly one kit across the snapshot.
-- Conflicting descriptions violate the catalog's primary key.
INSERT INTO kit_catalog (kit_code, kit_label, kit_family)
SELECT DISTINCT kit_code, kit_label, kit_family
FROM checkout_stage;

INSERT INTO kit_loan (ticket_code, kit_code, loan_day, days_out)
SELECT ticket_code, kit_code, loan_day, days_out
FROM checkout_stage;
