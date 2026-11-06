SELECT ABS(
    (SELECT COUNT_BIG(*) FROM {edw_raw}.checkout_snapshot) -
    (SELECT COUNT_BIG(*) FROM {edw}.fact_kit_loan)
);
