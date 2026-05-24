# Output Contract Discipline (V8.6)

Every skill body emits a structured `schema:` YAML block under `## Output contract`. Apply these rules once for the whole catalog.

## How the schema works

The schema is **authoritative** for what must be reported and what evidence each field requires:

- Each `field:` is a required section unless the entry sets `required: false`.
- Each `evidence_rule:` describes the minimum evidence the field must carry. `none` means no specific rule beyond the prose contract; otherwise the rule wins.
- The prose contract that follows the YAML block is the human-readable section list. It must match the schema 1:1.

If schema and prose ever conflict, **schema wins.** Open a PR against `source/skill-specs.json` to reconcile.

## How the output style works

Each skill's frontmatter declares an `output_style` (`evidence-led` or `concise-review`, defined in `output-styles/`). The style is **additive on top of the schema**:

- Schema controls **structure** — sections, fields, evidence rules.
- Style controls **tone, evidence discipline, and formatting** — how each field is rendered, how confidence is tagged, how findings are ranked.
- If style and schema conflict on structure, schema wins. If they conflict on tone, style wins.

Skill bodies should reference this file rather than re-explaining the relationship.
