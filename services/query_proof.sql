, invoices AS MATERIALIZED (
    SELECT i.* FROM records i JOIN customers c ON i.data->>'customer_id'=c.canonical_id
    WHERE i.entity='Invoice' AND (
        %(metric)s='cash_received' OR ((i.data->>'due_at')::date < %(as_of)s
                                      AND (i.data->>'issued_at')::date <= %(as_of)s))
), payments AS MATERIALIZED (
    SELECT p.* FROM records p JOIN invoices i ON p.data->>'invoice_id'=i.canonical_id
    WHERE p.entity='Payment' AND (p.data->>'paid_at')::date <= %(as_of)s
      AND (%(period_start)s::date IS NULL OR (p.data->>'paid_at')::date >= %(period_start)s)
), ticket_observations AS MATERIALIZED (
    SELECT * FROM canonical_records WHERE snapshot_id=ANY(%(snapshots)s::uuid[]) AND entity='Ticket'
), unsafe_tickets AS (
    SELECT canonical_id FROM ticket_observations GROUP BY canonical_id
    HAVING count(DISTINCT source_id)>1
        OR count(DISTINCT jsonb_build_array(data->'customer_id',data->'invoice_id'))>1
    UNION ALL SELECT min(canonical_id) FROM ticket_observations GROUP BY source_id
    HAVING count(DISTINCT canonical_id)>1
), tickets AS MATERIALIZED (
    SELECT t.* FROM (
        SELECT DISTINCT ON (source_id) * FROM ticket_observations
        ORDER BY source_id,retrieved_at DESC,record_id DESC
    ) t JOIN customers c ON t.data->>'customer_id'=c.canonical_id
    WHERE NOT EXISTS (SELECT 1 FROM unsafe_tickets)
), evidence AS (
    SELECT * FROM customers
    UNION ALL SELECT a.* FROM records a WHERE a.entity='Account'
        AND a.canonical_id IN (SELECT data->>'account_id' FROM customers)
    UNION ALL SELECT * FROM invoices
    UNION ALL SELECT i.* FROM records i WHERE i.entity='Invoice'
        AND NOT EXISTS (SELECT 1 FROM invoices counted WHERE counted.record_id=i.record_id)
        AND EXISTS (SELECT 1 FROM tickets t WHERE t.data->>'invoice_id'=i.canonical_id
                    AND t.data->>'customer_id'=i.data->>'customer_id')
    UNION ALL SELECT * FROM payments
    UNION ALL SELECT * FROM tickets
), source_rows AS (
SELECT e.entity,e.canonical_id,e.source_id,e.snapshot_id,e.retrieved_at,
       s.observed_at,e.mapping_version,e.ontology_version,e.family,
       (e.entity='Invoice' AND NOT EXISTS (
           SELECT 1 FROM records p WHERE p.entity='Payment' AND p.data->>'invoice_id'=e.canonical_id
           AND (p.data->>'paid_at')::date <= %(as_of)s)) AS payment_absence,
       CASE WHEN e.entity='Ticket' AND e.data->>'status' NOT IN ('closed','resolved')
         THEN jsonb_build_object('customer_id',e.data->>'customer_id',
                                 'status',e.data->>'status','subject',e.data->>'subject')
         ELSE NULL END AS ticket,
       ARRAY(SELECT 'Conflicting due dates: ' || e.source_id || ' reports ' ||
             (e.data->>'reported_due_at') || '; ' || i.source_id || ' bills ' || (i.data->>'due_at') ||
             '. Authority unresolved.'
             FROM records i WHERE e.entity='Ticket' AND i.entity='Invoice'
               AND i.canonical_id=e.data->>'invoice_id'
               AND i.data->>'customer_id'=e.data->>'customer_id'
               AND i.data->>'due_at'<>e.data->>'reported_due_at') AS conflicts
FROM evidence e JOIN snapshots s USING (snapshot_id)
ORDER BY e.entity,e.source_id
)
SELECT coalesce((SELECT jsonb_agg(source_rows) FROM source_rows), '[]'::jsonb) AS sources,
       ARRAY(SELECT 'Financial identity ambiguity; metric retrieval abstained.'
             WHERE EXISTS (SELECT 1 FROM ambiguous)
             UNION ALL SELECT 'Support identity ambiguity; ticket retrieval abstained.'
             WHERE EXISTS (SELECT 1 FROM unsafe_tickets)
             UNION ALL SELECT 'Unattributed invoice evidence exists; excluded rather than assigned to a client.'
             WHERE EXISTS (SELECT 1 FROM records WHERE entity='Invoice' AND data->>'customer_id' IS NULL))
       AS conflicts
