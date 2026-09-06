SELECT c.canonical_id AS customer_id, c.data->>'account_id' AS client_id,
       coalesce(sum(greatest(balance.amount, 0.00::numeric)), 0.00::numeric) AS observed_amount
FROM customers c
LEFT JOIN records i ON i.entity='Invoice' AND i.data->>'customer_id'=c.canonical_id
    AND (i.data->>'due_at')::date < %(as_of)s
    AND (i.data->>'issued_at')::date <= %(as_of)s
LEFT JOIN LATERAL (
    SELECT (i.data->>'amount')::numeric - coalesce(sum((p.data->>'amount')::numeric), 0.00::numeric) AS amount
    FROM records p WHERE p.entity='Payment' AND p.data->>'invoice_id'=i.canonical_id
      AND (p.data->>'paid_at')::date <= %(as_of)s
) balance ON TRUE
GROUP BY c.canonical_id,c.data->>'account_id'
ORDER BY c.canonical_id
