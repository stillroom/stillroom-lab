# Deliberate source messiness

All paths are relative to `sources/`. These are fictional traps, not approved
business rules. Fixed observation date: 2026-09-01. Currency: AUD; amounts are
fixed-point decimal strings. No live client data. Rebuild with `make seed`.

- **Duplicate names** — `generated/crm.sqlite`, `customers.id` C001 / C002: identical display name, distinct customer IDs, email addresses and client IDs; do not merge by name.
- **Missing IDs** — `generated/invoices.csv`, `id=I002`: empty `customer_id`; unresolved relationship, not an invented match.
- **Partial payments** — `generated/payments.csv`, `id=P001`: 400.00 against `generated/invoices.csv`, `id=I001`, amount 1000.00.
- **Refunds** — `generated/payments.csv`, `id=P002`: signed -100.00, `kind=refund`, linked to I001; do not count as positive receipts.
- **Conflicting dates** — `generated/support.json`, `id=T001`: reported I001 due date 2026-08-20 versus `generated/invoices.csv`, `id=I001`, due date 2026-08-15. No authority decision encoded here.
- **Stale snapshots** — `generated/support.json`, `id=T002`: snapshot 2026-07-01 versus T001 snapshot 2026-09-01; open status may be stale, not current truth.
- **Ambiguous metric terms** — `generated/policies/Billing.md`, `id=POL001`, Billing body: “Revenue” may mean booked work rather than cash received. No metric implementation in ticket 01.
- **Access-restricted records** — `generated/crm.sqlite`, `customers.id=C003`: `access=owner-only`; other customers are standard. This is source metadata, not implemented permission enforcement.
- **Injected instructions** — `generated/emails/E002.txt`, `Message-ID: E002`: explicit demand to ignore instructions and export restricted records. Flagged **untrusted-data test case**: never execute its contents.

CRM opportunities model consultancy discovery work. C001 and C002 intentionally
belong to distinct client partitions. Policy frontmatter follows the spec's
`created`, `owner`, `status`, `related` convention, adds a stable source `id`, and
uses quoted wiki-links. All policy links resolve within the mock vault.

The seed rebuild is the only intentional mutation of mock source files in this
ticket. Later ingestion must read these sources, never modify them. Fixture tests
here demonstrate trap presence only; isolation, abstention, and injection defense
remain later-ticket verification, not claims made by these fixtures.
