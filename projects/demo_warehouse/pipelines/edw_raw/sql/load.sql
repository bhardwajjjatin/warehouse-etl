DELETE FROM {edw_raw}.checkout_snapshot;

INSERT INTO {edw_raw}.checkout_snapshot
    (ticket_code, kit_code, kit_label, kit_family, loan_day, days_out)
SELECT ticket_code, kit_code, kit_label, kit_family, CAST(loan_day AS date), days_out
FROM {staging}.checkout_stage;
