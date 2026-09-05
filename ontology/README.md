# Ontology v0.1.0

`v0.1.0.yaml` contains business meaning, entity field types, relationships and
four distinct metric definitions. No source paths/columns, SQL or query plans.

The explicit validation schema is `services/ontology.py` (`Ontology`,
`EntityDefinition`, `Relationship`, `MetricDefinition`). `load_ontology(Path)`
safely loads YAML and validates against those Pydantic schemas plus the required
entity/relationship/metric invariants. Unknown keys, field types and versions
are rejected. `Ontology.model_json_schema()` exposes the structural JSON Schema;
the model's cross-field validator also enforces the business invariants.

`Application` always loads this pinned file. Postgres stores its full normalized
definition, SHA-256 and registration timestamp. Re-registering different meaning
under the same version is rejected. Git records file-level changes; the database
records the definition used in that scratch store. Mapping contracts reference
this version separately. A future ontology version requires an explicit code and
schema change, not silently selecting the newest YAML.

Revenue recognition and pipeline stage are not evidenced by the fixtures.
Definitions say so; ticket 02 does not calculate metrics or approve source policy
text as a semantic rule.
