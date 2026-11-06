SELECT ABS(
    (SELECT COUNT_BIG(*) FROM {staging}.checkout_stage) -
    (SELECT COUNT_BIG(*) FROM {edw_raw}.checkout_snapshot)
);
