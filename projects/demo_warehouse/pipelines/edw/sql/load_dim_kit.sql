INSERT INTO {edw}.dim_kit (kit_code, kit_label, kit_family)
SELECT DISTINCT kit_code, kit_label, kit_family
FROM {edw_raw}.checkout_snapshot;
