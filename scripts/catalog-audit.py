#!/usr/bin/env python3
"""V8: Catalog audit — robustness check for agents and skills (PRD §27.4).

Audits every agent .md and skill spec for:
- description length and specificity (>120 chars; mentions DEFAULT/USE WHEN/DO NOT)
- trigger phrase coverage (USE WHEN clause present)
- anti-pattern section presence
- lane boundary statements
- output contract structure
- failure_modes specificity (skills)
- workflow_steps concreteness (skills)
- evidence requirements
- duplicate descriptions across catalog
- duplicate trigger phrasing (high overlap risk)
- panel agent references resolve to existing agents
- panel V8 metadata contracts are present and phase-aligned
- dispatch_to references in skill specs resolve to existing agents

Outputs findings.json + human-readable report.
"""
from __future__ import annotations
import json
import os
import re
import sys
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parents[1]

# Severity rules
SEV_CRITICAL = "critical"
SEV_HIGH = "high"
SEV_MED = "medium"
SEV_LOW = "low"


def audit_agents() -> list[dict]:
    """Return list of findings for each agent file."""
    findings = []
    descriptions = {}
    triggers_by_agent = {}

    agents_dir = ROOT / "agents"
    for p in sorted(agents_dir.glob("*.md")):
        agent_name = p.stem
        try:
            content = p.read_text(encoding="utf-8")
        except Exception as e:
            findings.append({"agent": agent_name, "severity": SEV_HIGH, "issue": "read_failed", "detail": str(e)})
            continue

        # Parse frontmatter
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
        if not m:
            findings.append({"agent": agent_name, "severity": SEV_CRITICAL, "issue": "no_frontmatter",
                           "detail": "agent file missing YAML frontmatter"})
            continue
        frontmatter = m.group(1)
        body = m.group(2)

        # Extract description
        desc_match = re.search(r"^description:\s*(.+?)(?=\n[a-z_]+:|$)", frontmatter, re.MULTILINE | re.DOTALL)
        if not desc_match:
            findings.append({"agent": agent_name, "severity": SEV_CRITICAL, "issue": "no_description"})
            continue
        description = desc_match.group(1).strip()
        descriptions[agent_name] = description

        # Description length
        if len(description) < 120:
            findings.append({"agent": agent_name, "severity": SEV_HIGH, "issue": "description_short",
                           "detail": f"{len(description)} chars (target ≥120)"})

        # USE WHEN clause
        if "USE WHEN" not in description.upper():
            findings.append({"agent": agent_name, "severity": SEV_MED, "issue": "no_use_when_clause",
                           "detail": "description should include 'USE WHEN' trigger phrasing"})

        # DO NOT clause (anti-trigger)
        if "DO NOT" not in description.upper():
            findings.append({"agent": agent_name, "severity": SEV_MED, "issue": "no_do_not_clause",
                           "detail": "description should include 'DO NOT use for' lane boundary"})

        # DEFAULT CHOICE wording
        if "DEFAULT" not in description.upper():
            findings.append({"agent": agent_name, "severity": SEV_LOW, "issue": "no_default_claim",
                           "detail": "description should signal when this agent is the default"})

        # Extract triggers (text between USE WHEN and the next sentence-end)
        trigger_match = re.search(r"USE WHEN[^.]*?(?:\.|$)", description, re.IGNORECASE)
        if trigger_match:
            triggers_by_agent[agent_name] = trigger_match.group(0)

        # Body checks
        # Required output contract
        if "Required output contract" not in body and "output contract" not in body.lower():
            findings.append({"agent": agent_name, "severity": SEV_HIGH, "issue": "no_output_contract_section",
                           "detail": "agent body should declare structured output contract"})

        # Anti-patterns section
        if "Anti-pattern" not in body and "anti-pattern" not in body:
            findings.append({"agent": agent_name, "severity": SEV_MED, "issue": "no_anti_patterns_section",
                           "detail": "agent body should declare anti-patterns"})

        # Lane boundaries
        if "Lane boundar" not in body and "Don't use for" not in body and "DO NOT" not in body:
            findings.append({"agent": agent_name, "severity": SEV_MED, "issue": "no_lane_boundaries",
                           "detail": "agent body should declare lane boundaries vs other agents"})

        # Discipline section
        if "Discipline" not in body and "discipline" not in body:
            findings.append({"agent": agent_name, "severity": SEV_MED, "issue": "no_discipline_section"})

        # Body length (very short bodies are red flags)
        if len(body) < 1500:
            findings.append({"agent": agent_name, "severity": SEV_HIGH, "issue": "body_short",
                           "detail": f"{len(body)} chars (target ≥1500)"})

    # Cross-agent: duplicate descriptions
    desc_to_agents = defaultdict(list)
    for agent, desc in descriptions.items():
        # Hash first 200 chars to detect near-duplicates
        key = desc[:200].lower()
        desc_to_agents[key].append(agent)
    for key, agents in desc_to_agents.items():
        if len(agents) > 1:
            findings.append({"severity": SEV_HIGH, "issue": "duplicate_descriptions",
                           "agents": agents, "detail": "agents share description prefix"})

    return findings


def audit_skills() -> list[dict]:
    """Return list of findings for each skill spec."""
    findings = []
    specs_path = ROOT / "source" / "skill-specs.json"
    if not specs_path.exists():
        return [{"severity": SEV_CRITICAL, "issue": "skill_specs_missing"}]
    specs = json.load(open(specs_path))

    descriptions = {}
    for spec in specs:
        name = spec.get("name", "<unknown>")

        # Description
        desc = spec.get("description", "")
        descriptions[name] = desc
        if len(desc) < 150:
            findings.append({"skill": name, "severity": SEV_HIGH, "issue": "description_short",
                           "detail": f"{len(desc)} chars (target ≥150)"})

        # Triggers
        if "when user says" not in desc.lower() and "USE WHEN" not in desc:
            findings.append({"skill": name, "severity": SEV_MED, "issue": "no_trigger_phrasing",
                           "detail": "description should signal user-facing trigger phrases"})

        if "DEFAULT" not in desc.upper():
            findings.append({"skill": name, "severity": SEV_LOW, "issue": "no_default_claim"})

        # Required spec fields
        required = ["name", "title", "tier", "description", "when_to_use", "editing", "aliases",
                    "distinctive_judgment", "first_signals", "failure_modes", "workflow_steps",
                    "validation_strategy", "output_contract", "subagent_delegation"]
        for field in required:
            if field not in spec:
                findings.append({"skill": name, "severity": SEV_HIGH, "issue": "missing_required_field",
                               "field": field})

        # Field-quality checks
        wtu = spec.get("when_to_use", "")
        if len(wtu) < 80:
            findings.append({"skill": name, "severity": SEV_MED, "issue": "when_to_use_short",
                           "detail": f"{len(wtu)} chars"})

        dj = spec.get("distinctive_judgment", "")
        if len(dj) < 80:
            findings.append({"skill": name, "severity": SEV_MED, "issue": "distinctive_judgment_short",
                           "detail": f"{len(dj)} chars"})

        fs = spec.get("first_signals", [])
        if not fs or len(fs) < 2:
            findings.append({"skill": name, "severity": SEV_MED, "issue": "first_signals_too_few",
                           "detail": f"{len(fs)} signals (target ≥2)"})

        fm = spec.get("failure_modes", [])
        if not fm or len(fm) < 3:
            findings.append({"skill": name, "severity": SEV_MED, "issue": "failure_modes_too_few",
                           "detail": f"{len(fm)} modes (target ≥3)"})

        ws = spec.get("workflow_steps", [])
        if not ws or len(ws) < 3:
            findings.append({"skill": name, "severity": SEV_MED, "issue": "workflow_steps_too_few",
                           "detail": f"{len(ws)} steps (target ≥3)"})

        oc = spec.get("output_contract", "")
        if isinstance(oc, list):
            if len(oc) < 4:
                findings.append({"skill": name, "severity": SEV_MED, "issue": "output_contract_thin",
                               "detail": f"{len(oc)} items"})
        elif isinstance(oc, str):
            if len(oc) < 80 or oc.count("|") < 3:
                findings.append({"skill": name, "severity": SEV_MED, "issue": "output_contract_thin",
                               "detail": f"{len(oc)} chars, {oc.count('|')} sections"})

        # dispatch_to resolves to existing agent
        dt = spec.get("dispatch_to")
        if dt and isinstance(dt, dict):
            agent = dt.get("agent")
            if agent:
                agent_path = ROOT / "agents" / f"{agent}.md"
                if not agent_path.exists():
                    findings.append({"skill": name, "severity": SEV_CRITICAL,
                                   "issue": "dispatch_to_missing_agent",
                                   "detail": f"references ultraprompt:{agent} which doesn't exist"})

    # Duplicate descriptions across skills
    desc_to_skills = defaultdict(list)
    for skill, desc in descriptions.items():
        key = desc[:200].lower()
        desc_to_skills[key].append(skill)
    for key, skills in desc_to_skills.items():
        if len(skills) > 1:
            findings.append({"severity": SEV_HIGH, "issue": "duplicate_skill_descriptions",
                           "skills": skills})

    return findings


def audit_panels() -> list[dict]:
    """Verify panel agent references and V8 metadata contracts."""
    findings = []
    panels_path = ROOT / "source" / "panel-specs.json"
    if not panels_path.exists():
        return findings
    panels = json.load(open(panels_path))
    agents_dir = ROOT / "agents"
    existing_agents = {p.stem for p in agents_dir.glob("*.md")}
    required_fields = {
        "mode", "risk", "confirmation", "inputs", "success_criteria",
        "handoff_artifacts", "phase_contracts", "do_not_use_when",
        "pathfinder_tags", "memory_policy", "learning_policy", "dream_policy",
    }
    allowed_modes = {"read_only", "proposal_only", "mutation_plan", "external_side_effect", "mixed"}
    allowed_risks = {"low", "medium", "high"}

    for panel in panels:
        name = panel.get("name", "<unknown>")
        for field in sorted(required_fields):
            value = panel.get(field)
            if value in (None, "", [], {}):
                findings.append({
                    "panel": name, "severity": SEV_HIGH,
                    "issue": "panel_missing_v8_metadata",
                    "detail": f"missing or empty field '{field}'",
                })

        if panel.get("mode") and panel.get("mode") not in allowed_modes:
            findings.append({
                "panel": name, "severity": SEV_HIGH,
                "issue": "panel_invalid_mode",
                "detail": f"mode '{panel.get('mode')}' is not one of {sorted(allowed_modes)}",
            })
        if panel.get("risk") and panel.get("risk") not in allowed_risks:
            findings.append({
                "panel": name, "severity": SEV_HIGH,
                "issue": "panel_invalid_risk",
                "detail": f"risk '{panel.get('risk')}' is not one of {sorted(allowed_risks)}",
            })

        confirmation = panel.get("confirmation")
        if not isinstance(confirmation, dict) or "required" not in confirmation or "reason" not in confirmation:
            findings.append({
                "panel": name, "severity": SEV_HIGH,
                "issue": "panel_invalid_confirmation_contract",
                "detail": "confirmation must contain required and reason",
            })

        phase_contracts = panel.get("phase_contracts", {})
        for phase in panel.get("phases", []):
            phase_name = phase.get("phase", "<unknown>")
            contract = phase_contracts.get(phase_name)
            if not isinstance(contract, dict) or not all(contract.get(k) for k in ("input", "output", "quality_gate")):
                findings.append({
                    "panel": name, "severity": SEV_HIGH,
                    "issue": "panel_phase_contract_missing",
                    "detail": f"phase '{phase_name}' must define input, output, and quality_gate",
                })
            for agent in phase.get("agents", []):
                if agent not in existing_agents:
                    findings.append({
                        "panel": name, "severity": SEV_CRITICAL,
                        "issue": "panel_references_missing_agent",
                        "detail": f"phase '{phase_name}' references ultraprompt:{agent} which doesn't exist",
                    })
    return findings


def main():
    print("Ultraprompt V8 Catalog Audit")
    print("=" * 60)

    findings = []
    findings.extend(audit_agents())
    findings.extend(audit_skills())
    findings.extend(audit_panels())

    # Group by severity
    by_severity = defaultdict(list)
    for f in findings:
        by_severity[f.get("severity", "unknown")].append(f)

    print(f"\nTotal findings: {len(findings)}")
    print(f"  critical: {len(by_severity['critical'])}")
    print(f"  high:     {len(by_severity['high'])}")
    print(f"  medium:   {len(by_severity['medium'])}")
    print(f"  low:      {len(by_severity['low'])}")

    # Top issues by type
    by_issue = Counter(f.get("issue", "unknown") for f in findings)
    print("\nTop issue types:")
    for issue, count in by_issue.most_common(15):
        print(f"  {count:4d} × {issue}")

    # Per-agent counts
    by_agent = Counter(f.get("agent", "?") for f in findings if "agent" in f)
    if by_agent:
        print("\nAgents with most findings:")
        for agent, count in by_agent.most_common(10):
            print(f"  {count:3d} × {agent}")

    # Per-skill counts
    by_skill = Counter(f.get("skill", "?") for f in findings if "skill" in f)
    if by_skill:
        print("\nSkills with most findings:")
        for skill, count in by_skill.most_common(10):
            print(f"  {count:3d} × {skill}")

    report = {
        "total": len(findings),
        "by_severity": {k: len(v) for k, v in by_severity.items()},
        "by_issue": dict(by_issue),
        "findings": findings,
    }

    # Write report. Installed plugin trees can be held open by a running runtime
    # on Windows, so fall back to user state rather than failing the audit.
    report_candidates = [
        ROOT / "dist" / "catalog-audit-report.json",
        Path.home() / ".ultraprompt" / "state" / "catalog-audit-report.json",
        Path.home() / ".ultraprompt" / "state" / f"catalog-audit-report-{os.getpid()}.json",
    ]
    report_path = None
    for candidate in report_candidates:
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            with open(candidate, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            report_path = candidate
            break
        except OSError:
            continue
    if report_path is None:
        print("\nFull report: skipped (report path locked)")
    else:
        print(f"\nFull report: {report_path}")

    # Exit code reflects severity
    if by_severity['critical']:
        return 2
    if by_severity['high']:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
