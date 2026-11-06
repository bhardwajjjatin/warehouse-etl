SELECT COUNT_BIG(*)
FROM {edw}.fact_kit_loan AS fact
LEFT JOIN {edw}.dim_kit AS kit ON kit.kit_key = fact.kit_key
LEFT JOIN {edw}.dim_date AS calendar ON calendar.date_key = fact.loan_date_key
WHERE kit.kit_key IS NULL OR calendar.date_key IS NULL;
