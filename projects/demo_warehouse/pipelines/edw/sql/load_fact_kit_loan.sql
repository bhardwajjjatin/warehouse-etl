INSERT INTO {edw}.fact_kit_loan (ticket_code, kit_key, loan_date_key, days_out)
SELECT snapshot.ticket_code, kit.kit_key, calendar.date_key, snapshot.days_out
FROM {edw_raw}.checkout_snapshot AS snapshot
JOIN {edw}.dim_kit AS kit ON kit.kit_code = snapshot.kit_code
JOIN {edw}.dim_date AS calendar ON calendar.calendar_date = snapshot.loan_day;
