SELECT c.canonical_id AS customer_id, c.data->>'account_id' AS client_id,
       coalesce(sum((p.data->>'amount')::numeric), 0.00::numeric) AS observed_amount
FROM customers c
LEFT JOIN records i ON i.entity='Invoice' AND i.data->>'customer_id'=c.canonical_id
LEFT JOIN records p ON p.entity='Payment' AND p.data->>'invoice_id'=i.canonical_id
    AND (p.data->>'paid_at')::date <= %(as_of)s
    AND (%(period_start)s::date IS NULL OR (p.data->>'paid_at')::date >= %(period_start)s)
GROUP BY c.canonical_id,c.data->>'account_id'
ORDER BY c.canonical_id
