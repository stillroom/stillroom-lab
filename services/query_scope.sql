WITH observations AS MATERIALIZED (
    SELECT * FROM canonical_records WHERE snapshot_id=ANY(%(snapshots)s::uuid[])
      AND entity IN ('Account','Customer','Invoice','Payment')
), ambiguous AS MATERIALIZED (
    -- References have no tenant key. Check history BEFORE choosing latest rows:
    -- a reused source ID must never move old facts into a new client partition.
    SELECT entity,canonical_id FROM observations
    GROUP BY entity,canonical_id
    HAVING count(DISTINCT source_id) > 1
        OR count(DISTINCT jsonb_build_array(data->'account_id',data->'customer_id',
                                           data->'invoice_id',data->'access')) > 1
    UNION ALL
    SELECT entity,min(canonical_id) FROM observations
    GROUP BY entity,source_id
    HAVING count(DISTINCT canonical_id) > 1
), records AS MATERIALIZED (
    SELECT DISTINCT ON (entity,source_id) * FROM observations
    ORDER BY entity,source_id,retrieved_at DESC,record_id DESC
), customers AS MATERIALIZED (
    SELECT c.* FROM records c WHERE c.entity='Customer'
      AND c.data->>'account_id'=%(client_id)s
      AND (c.data->>'access'='standard' OR
           (c.data->>'access'='owner-only' AND %(role)s='owner'))
      AND EXISTS (SELECT 1 FROM records a WHERE a.entity='Account'
                  AND a.canonical_id=c.data->>'account_id')
      -- Global abstention is deliberately conservative: do not turn an
      -- unresolved financial join into an apparently zero customer balance.
      AND NOT EXISTS (SELECT 1 FROM ambiguous)
)
