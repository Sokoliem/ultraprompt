// Ultraprompt Dashboard — V8

const STATE = {
  catalog: null,
  selected: null, // { kind, name }
  audit: null,
  bench: null,
  cognitive: null,
  searchQuery: "",
};

// ─── API client ────────────────────────────────────────────────────────────
const api = {
  async catalog() { return (await fetch("/api/catalog")).json(); },
  async entity(kind, name) {
    return (await fetch(`/api/catalog/${kind}/${encodeURIComponent(name)}`)).json();
  },
  async audit() { return (await fetch("/api/audit")).json(); },
  async bench() { return (await fetch("/api/router-bench")).json(); },
  async cognitiveHealth() { return (await fetch("/api/cognitive/health")).json(); },
  async invocations(limit = 50) {
    return (await fetch(`/api/invocations?limit=${limit}`)).json();
  },
  async missionState() { return (await fetch("/api/mission-state")).json(); },
};

// ─── Helpers ───────────────────────────────────────────────────────────────
const KIND_LABELS = {
  agents: "Agents",
  skills: "Skills",
  panels: "Panels",
  mcp_tools: "MCP Tools",
  commands: "Commands",
  artifact_schemas: "Artifact Schemas",
};

const KIND_ORDER = ["skills", "agents", "panels", "mcp_tools", "commands", "artifact_schemas"];

function fmtTime(ts) {
  if (!ts) return "-";
  const ms = typeof ts === "number" ? ts * 1000 : Date.parse(ts);
  if (!Number.isFinite(ms)) return "-";
  const d = new Date(ms);
  const now = new Date();
  const diff = (now - d) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return d.toLocaleDateString();
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") {
      node.addEventListener(k.slice(2).toLowerCase(), v);
    } else if (v !== null && v !== undefined) {
      node.setAttribute(k, v);
    }
  }
  for (const c of children) {
    if (c == null) continue;
    if (typeof c === "string") node.appendChild(document.createTextNode(c));
    else node.appendChild(c);
  }
  return node;
}

function highlightMatch(text, query) {
  if (!query) return text;
  const q = query.toLowerCase();
  const idx = text.toLowerCase().indexOf(q);
  if (idx < 0) return text;
  return [
    text.slice(0, idx),
    el("strong", { style: "color: var(--accent)" }, text.slice(idx, idx + q.length)),
    text.slice(idx + q.length),
  ];
}

// ─── <up-stats-card> ───────────────────────────────────────────────────────
class StatsCard extends HTMLElement {
  render() {
    if (!STATE.catalog) {
      this.innerHTML = `<div style="padding:20px;color:var(--fg-faint);font-size:12px">Loading…</div>`;
      return;
    }
    const s = STATE.catalog.stats;
    this.innerHTML = "";
    const grid = el("div", { class: "stats-grid" });
    for (const kind of KIND_ORDER) {
      const key = kind === "mcp_tools" ? "mcp_tools" :
                  kind === "artifact_schemas" ? "artifact_schemas" : kind;
      const num = s[key] ?? 0;
      const label = KIND_LABELS[kind];
      grid.appendChild(
        el("div", { class: "stat", "data-kind": kind, onclick: () => scrollToKind(kind) },
          el("div", { class: "stat-num" }, String(num)),
          el("div", { class: "stat-label" }, label)
        )
      );
    }
    this.appendChild(grid);
  }
}
customElements.define("up-stats-card", StatsCard);

// ─── <up-catalog-tree> ─────────────────────────────────────────────────────
class CatalogTree extends HTMLElement {
  constructor() { super(); this._collapsed = new Set(); }
  render() {
    if (!STATE.catalog) return;
    this.innerHTML = "";
    const q = STATE.searchQuery.toLowerCase();
    for (const kind of KIND_ORDER) {
      const items = (STATE.catalog[kind] || []).filter(item => {
        if (!q) return true;
        const hay = [item.name, item.title, item.description, item.family]
          .filter(Boolean).join(" ").toLowerCase();
        return hay.includes(q);
      });
      if (items.length === 0 && q) continue;

      const collapsed = this._collapsed.has(kind);
      const group = el("div", {
        class: "tree-group",
        "data-kind": kind,
        "data-collapsed": collapsed,
      });
      const heading = el("div", {
        class: "tree-heading",
        onclick: () => {
          if (this._collapsed.has(kind)) this._collapsed.delete(kind);
          else this._collapsed.add(kind);
          this.render();
        }
      },
        el("span", { class: "tree-heading-chevron" }, "▾"),
        document.createTextNode(KIND_LABELS[kind]),
        el("span", { class: "tree-heading-count" }, ` (${items.length})`)
      );
      group.appendChild(heading);

      const list = el("div", { class: "tree-items" });
      for (const item of items) {
        const isSelected = STATE.selected
          && STATE.selected.kind === kind
          && STATE.selected.name === item.name;
        const row = el("div", {
          class: "tree-item",
          "data-kind": kind,
          "data-selected": isSelected,
          onclick: () => selectEntity(kind, item.name),
        },
          el("span", { class: "tree-item-dot" }),
          el("span", { class: "tree-item-name" }, item.name)
        );
        if (item.tier) {
          row.appendChild(el("span", { class: "tree-tier", "data-tier": item.tier }, item.tier));
        }
        list.appendChild(row);
      }
      group.appendChild(list);
      this.appendChild(group);
    }
  }
}
customElements.define("up-catalog-tree", CatalogTree);

// ─── <up-detail-pane> ──────────────────────────────────────────────────────
class DetailPane extends HTMLElement {
  async render() {
    if (!STATE.selected) {
      this.renderHome();
      return;
    }
    const { kind, name } = STATE.selected;
    const entity = await api.entity(kind, name);
    this.innerHTML = "";

    const header = el("div", { class: "detail-header" },
      el("h2", { class: "detail-name" }, entity.name),
      el("span", { class: "detail-kind-badge", "data-kind": kind }, KIND_LABELS[kind] || kind)
    );
    this.appendChild(header);

    const metaParts = [];
    if (entity.tier) metaParts.push(`tier: ${entity.tier}`);
    if (entity.family) metaParts.push(`family: ${entity.family}`);
    if (entity.dispatch_to?.agent) metaParts.push(`dispatch → ${entity.dispatch_to.agent}`);
    if (entity.color) metaParts.push(`color: ${entity.color}`);
    if (entity.path) metaParts.push(entity.path);
    if (entity.dispatch_count !== undefined) {
      metaParts.push(`${entity.dispatch_count} dispatches across ${entity.phase_count} phases`);
    }
    if (entity.estimated_cost) metaParts.push(`cost: ${entity.estimated_cost}`);
    if (entity.estimated_time_minutes) metaParts.push(`~${entity.estimated_time_minutes} min`);

    if (metaParts.length) {
      const meta = el("div", { class: "detail-meta" });
      for (const part of metaParts) meta.appendChild(el("span", {}, part));
      this.appendChild(meta);
    }

    // Description
    if (entity.description) {
      this.appendChild(this._section("Description",
        el("div", { class: "detail-description" }, entity.description)
      ));
    }

    // Use cases (extracted trigger phrases)
    if (entity.use_cases && entity.use_cases.length) {
      const tags = el("div", { class: "use-cases" });
      for (const uc of entity.use_cases) {
        tags.appendChild(el("span", { class: "use-case" }, `"${uc}"`));
      }
      this.appendChild(this._section("Trigger phrases", tags));
    }

    // Skill-specific
    if (entity.distinctive_judgment) {
      this.appendChild(this._section("Distinctive judgment",
        el("div", { class: "detail-description" }, entity.distinctive_judgment)
      ));
    }
    if (entity.when_to_use) {
      this.appendChild(this._section("When to use",
        el("div", { class: "detail-description" }, entity.when_to_use)
      ));
    }
    if (entity.first_signals && entity.first_signals.length) {
      this.appendChild(this._section("First signals",
        this._list(entity.first_signals)
      ));
    }
    if (entity.failure_modes && entity.failure_modes.length) {
      this.appendChild(this._section("Failure modes",
        this._list(entity.failure_modes)
      ));
    }
    if (entity.workflow_steps && entity.workflow_steps.length) {
      this.appendChild(this._section("Workflow steps",
        this._list(entity.workflow_steps, true)
      ));
    }
    if (entity.output_contract && typeof entity.output_contract === "string") {
      this.appendChild(this._section("Output contract",
        el("pre", {}, entity.output_contract)
      ));
    } else if (entity.output_contract) {
      this.appendChild(this._section("Output contract",
        el("pre", {}, entity.output_contract)
      ));
    }
    if (entity.subagent_delegation) {
      this.appendChild(this._section("Subagent delegation",
        el("div", { class: "detail-description" }, entity.subagent_delegation)
      ));
    }

    // Agent-specific (lane boundaries, anti-patterns)
    if (entity.lane_boundaries) {
      this.appendChild(this._section("Lane boundaries",
        el("pre", {}, entity.lane_boundaries)
      ));
    }
    if (entity.anti_patterns) {
      this.appendChild(this._section("Anti-patterns",
        el("pre", {}, entity.anti_patterns)
      ));
    }
    if (kind === "agents" && entity.tools && entity.tools.length) {
      const tags = el("div", { class: "use-cases" });
      for (const t of entity.tools) tags.appendChild(el("span", { class: "use-case" }, t));
      this.appendChild(this._section("Available tools", tags));
    }

    // Panel-specific contract and phases
    if (kind === "panels") {
      const confirmation = entity.confirmation || {};
      this.appendChild(this._section("Panel contract", this._kvGrid([
        ["Mode", entity.mode],
        ["Risk", entity.risk],
        ["Confirmation", confirmation.required ? `required: ${confirmation.reason || ""}` : `not required: ${confirmation.reason || ""}`],
        ["Output", entity.output_artifact],
        ["Resume", entity.resume_behavior],
        ["Cancel", entity.cancel_behavior],
      ])));
      if (entity.inputs && entity.inputs.length) {
        this.appendChild(this._section("Inputs", this._list(entity.inputs)));
      }
      if (entity.success_criteria && entity.success_criteria.length) {
        this.appendChild(this._section("Success criteria", this._list(entity.success_criteria)));
      }
      if (entity.handoff_artifacts && entity.handoff_artifacts.length) {
        this.appendChild(this._section("Handoff artifacts", this._tagList(entity.handoff_artifacts)));
      }
      if (entity.pathfinder_tags && entity.pathfinder_tags.length) {
        this.appendChild(this._section("Pathfinder tags", this._tagList(entity.pathfinder_tags)));
      }
      if (entity.do_not_use_when) {
        this.appendChild(this._section("Do not use when",
          el("div", { class: "detail-description" }, entity.do_not_use_when)
        ));
      }
      this.appendChild(this._section("Cognitive policies", this._policyGrid(entity)));
    }

    if (kind === "panels" && entity.phases) {
      const flow = el("div", { class: "phases-flow" });
      for (const ph of entity.phases) {
        const phaseContract = (entity.phase_contracts || {})[ph.phase] || {};
        const card = el("div", {
          class: "phase-card",
          "data-parallel": String(ph.parallel),
        },
          el("div", { class: "phase-name" }, ph.phase),
          el("div", { class: "phase-purpose" }, ph.purpose || ""),
        );
        const agentList = el("div", { class: "phase-agents" });
        for (const a of ph.agents) {
          agentList.appendChild(el("div", {
            class: "phase-agent",
            onclick: () => selectEntity("agents", a),
          }, `-> ${a}`));
        }
        card.appendChild(agentList);
        if (Object.keys(phaseContract).length) {
          card.appendChild(el("div", { class: "phase-contract" },
            el("div", { class: "phase-contract-row" },
              el("span", {}, "input"),
              el("strong", {}, phaseContract.input || "")
            ),
            el("div", { class: "phase-contract-row" },
              el("span", {}, "output"),
              el("strong", {}, phaseContract.output || "")
            ),
            el("div", { class: "phase-contract-row" },
              el("span", {}, "gate"),
              el("strong", {}, phaseContract.quality_gate || "")
            )
          ));
        }
        flow.appendChild(card);
      }
      this.appendChild(this._section("Phased dispatch", flow));
    }

    // MCP tool-specific
    if (kind === "mcp_tools" && entity.input_schema) {
      this.appendChild(this._section("Input schema",
        el("pre", {}, JSON.stringify(entity.input_schema, null, 2))
      ));
    }

    // Artifact schema-specific
    if (kind === "artifact_schemas" && entity.schema) {
      this.appendChild(this._section("Schema",
        el("pre", {}, JSON.stringify(entity.schema, null, 2))
      ));
    }

    // Recent invocations
    if (entity.recent_invocations && entity.recent_invocations.length) {
      const list = el("div", { class: "invocations-list" });
      for (const inv of entity.recent_invocations.slice(0, 10)) {
        list.appendChild(el("div", { class: "invocation" },
          el("span", { class: "invocation-time" }, fmtTime(inv.ts)),
          el("span", { class: "invocation-kind" }, inv.kind),
          el("span", {}, inv.source || "")
        ));
      }
      this.appendChild(this._section("Recent invocations", list));
    } else {
      this.appendChild(this._section("Recent invocations",
        el("div", { class: "invocations-list-empty" }, "no invocations yet")
      ));
    }
  }

  _section(title, body) {
    return el("div", { class: "detail-section" },
      el("div", { class: "detail-section-title" }, title),
      body
    );
  }

  _kvGrid(rows) {
    const grid = el("div", { class: "panel-meta-grid" });
    for (const [label, value] of rows) {
      if (value === undefined || value === null || value === "") continue;
      grid.appendChild(el("div", { class: "panel-meta-row" },
        el("span", {}, label),
        el("strong", {}, Array.isArray(value) ? value.join(", ") : String(value))
      ));
    }
    return grid;
  }

  _tagList(items) {
    const tags = el("div", { class: "use-cases" });
    for (const item of items) tags.appendChild(el("span", { class: "use-case" }, String(item)));
    return tags;
  }

  _policyGrid(entity) {
    const grid = el("div", { class: "policy-grid" });
    const policies = [
      ["Memory", entity.memory_policy],
      ["Learning", entity.learning_policy],
      ["Dream", entity.dream_policy],
    ];
    for (const [label, policy] of policies) {
      if (!policy) continue;
      const flags = Object.entries(policy)
        .filter(([key]) => key !== "notes")
        .map(([key, value]) => `${key}: ${String(value)}`)
        .join(" | ");
      grid.appendChild(el("div", { class: "policy-card" },
        el("div", { class: "policy-title" }, label),
        el("div", { class: "policy-flags" }, flags),
        el("div", { class: "policy-notes" }, policy.notes || "")
      ));
    }
    return grid;
  }

  _list(items, ordered = false) {
    const tag = ordered ? "ol" : "ul";
    const list = el(tag, { style: "margin: 0; padding-left: 20px; color: var(--fg-dim); font-size: 13px;" });
    for (const it of items) list.appendChild(el("li", { style: "margin-bottom: 4px;" }, String(it)));
    return list;
  }

  async renderHome() {
    this.innerHTML = "";
    if (!STATE.catalog) return;

    const home = el("div", { class: "home-view" });
    home.appendChild(el("h1", { class: "home-title" }, "Ultraprompt"));
    home.appendChild(el("p", { class: "home-tagline" },
      `${STATE.catalog.stats.total_items} catalog items across ${KIND_ORDER.length} kinds. ` +
      `Plugin version ${STATE.catalog.version}.`
    ));

    // Audit section
    const auditBox = el("div", { class: "home-section" });
    auditBox.appendChild(el("div", { class: "home-section-title" }, "Catalog audit"));
    const auditGrid = el("div", { class: "audit-summary" });
    if (STATE.audit) {
      for (const sev of ["critical", "high", "medium", "low"]) {
        const count = STATE.audit.by_severity?.[sev] ?? 0;
        auditGrid.appendChild(el("div", { class: "audit-cell", "data-sev": sev },
          el("div", { class: "audit-cell-num", "data-zero": String(count === 0) }, String(count)),
          el("div", { class: "audit-cell-label" }, sev)
        ));
      }
    }
    auditBox.appendChild(auditGrid);
    home.appendChild(auditBox);

    // Router bench section
    if (STATE.bench && STATE.bench.positive) {
      const benchBox = el("div", { class: "home-section" });
      benchBox.appendChild(el("div", { class: "home-section-title" }, "Router bench"));
      const t1 = STATE.bench.positive.top_1;
      const t3 = STATE.bench.positive.top_3;
      const adv = STATE.bench.adversarial?.rejected;
      if (t1) benchBox.appendChild(el("div", { class: "bench-row" },
        el("span", {}, `Top-1 (positive, ${t1.total} cases)`),
        el("span", { class: "bench-pct", "data-pass": String(t1.pct >= 90) },
          `${t1.pass}/${t1.total} (${t1.pct}%)`)
      ));
      if (t3) benchBox.appendChild(el("div", { class: "bench-row" },
        el("span", {}, `Top-3 (positive, ${t3.total} cases)`),
        el("span", { class: "bench-pct", "data-pass": String(t3.pct >= 100) },
          `${t3.pass}/${t3.total} (${t3.pct}%)`)
      ));
      if (adv) benchBox.appendChild(el("div", { class: "bench-row" },
        el("span", {}, `Adversarial (${adv.total} cases)`),
        el("span", { class: "bench-pct", "data-pass": String(adv.pct >= 100) },
          `${adv.pass}/${adv.total} rejected (${adv.pct}%)`)
      ));
      home.appendChild(benchBox);
    }

    if (STATE.cognitive) {
      const cogBox = el("div", { class: "home-section" });
      cogBox.appendChild(el("div", { class: "home-section-title" }, "Cognitive control plane"));
      const graph = STATE.cognitive.graph?.summary || {};
      const rows = [
        ["Graph", `${graph.node_count ?? 0} nodes / ${graph.edge_count ?? 0} edges`, STATE.cognitive.graph?.ok],
        ["Memory", `${STATE.cognitive.memory?.total ?? 0} records`, STATE.cognitive.memory?.ok],
        ["Dreams", `${STATE.cognitive.dreams?.report_count ?? 0} reports`, STATE.cognitive.dreams?.ok],
        ["Learning", `${STATE.cognitive.learning?.total ?? 0} candidates`, STATE.cognitive.learning?.ok],
        ["Events", `${STATE.cognitive.events?.total ?? 0} events`, STATE.cognitive.events?.ok],
        ["Pathfinder", `${STATE.cognitive.pathfinder?.top1 ?? 0}/${STATE.cognitive.pathfinder?.total ?? 0} top-1`, STATE.cognitive.pathfinder?.ok],
      ];
      for (const [label, value, ok] of rows) {
        cogBox.appendChild(el("div", { class: "bench-row" },
          el("span", {}, label),
          el("span", { class: "bench-pct", "data-pass": String(Boolean(ok)) }, value)
        ));
      }
      home.appendChild(cogBox);
    }

    // Family breakdown
    const famBox = el("div", { class: "home-section" });
    famBox.appendChild(el("div", { class: "home-section-title" }, "Skill families"));
    const families = STATE.catalog.stats.by_family || {};
    for (const [fam, count] of Object.entries(families).sort((a, b) => b[1] - a[1])) {
      famBox.appendChild(el("div", { class: "bench-row" },
        el("span", { style: "color: var(--fg-dim)" }, fam),
        el("span", { class: "bench-pct" }, `${count} skills`)
      ));
    }
    home.appendChild(famBox);

    home.appendChild(el("div", { class: "home-section" },
      el("div", { class: "home-section-title" }, "Quick start"),
      el("div", { class: "detail-description" },
        "Search the catalog with Ctrl+K, or click any item in the left tree. " +
        "Live invocations stream into the right panel as you use Ultraprompt in Claude Code or Codex."
      )
    ));

    this.appendChild(home);
  }
}
customElements.define("up-detail-pane", DetailPane);

function eventSummary(rec) {
  if (rec.type) {
    const subject = rec.skill || rec.tool || rec.agent || rec.command || rec.hook || rec.repo || rec.worktree;
    const detail = rec.decision || rec.outcome || rec.status || rec.phase;
    return [rec.type, subject, detail].filter(Boolean).join(" - ");
  }
  if (rec.event) {
    const subject = rec.tool_name || rec.tool || rec.command || rec.cwd || rec.repo;
    return [rec.event, subject].filter(Boolean).join(" - ");
  }
  if (rec.kind) return rec.kind;
  if (rec.text) return rec.text;
  if (rec.what_was_validated) return rec.what_was_validated;
  if (rec.artifact_type) return rec.artifact_type;
  if (rec.from && rec.to) return `${rec.from} -> ${rec.to} (${rec.relation})`;
  return JSON.stringify(rec).slice(0, 100);
}

// ─── <up-activity-feed> ────────────────────────────────────────────────────
class ActivityFeed extends HTMLElement {
  constructor() {
    super();
    this.events = [];
    this.max = 100;
  }
  connectedCallback() {
    this.innerHTML = `
      <div class="feed-header">
        <div class="feed-title">Live Activity</div>
        <div class="feed-subtitle" id="feedSubtitle">no events yet</div>
      </div>
      <div class="feed-list" id="feedList">
        <div class="feed-empty">Run a skill or agent in Claude Code — events stream here in real time.</div>
      </div>
    `;
  }
  push(event) {
    this.events.unshift(event);
    if (this.events.length > this.max) this.events.pop();
    this.render();
  }
  render() {
    const list = this.querySelector("#feedList");
    const sub = this.querySelector("#feedSubtitle");
    if (!list) return;
    if (!this.events.length) return;
    sub.textContent = `${this.events.length} event${this.events.length === 1 ? "" : "s"}`;
    list.innerHTML = "";
    for (const ev of this.events) {
      const rec = ev.record || {};
      const summary = eventSummary(rec);
      list.appendChild(el("div", {
        class: "feed-event",
        onclick: () => console.log("event:", ev),
      },
        el("div", { class: "feed-event-header" },
          el("span", { class: "feed-event-kind", "data-kind": ev.kind }, ev.kind),
          el("span", { class: "feed-event-time" }, fmtTime(ev.ts))
        ),
        el("div", { class: "feed-event-body" }, summary)
      ));
    }
  }
}
customElements.define("up-activity-feed", ActivityFeed);

// ─── State actions ─────────────────────────────────────────────────────────
async function selectEntity(kind, name) {
  STATE.selected = { kind, name };
  history.pushState({}, "", `?kind=${kind}&name=${encodeURIComponent(name)}`);
  document.querySelectorAll(".tree-item").forEach(it => it.removeAttribute("data-selected"));
  document.getElementById("tree").render();
  await document.getElementById("detail").render();
}

function scrollToKind(kind) {
  const group = document.querySelector(`.tree-group[data-kind="${kind}"]`);
  if (group) group.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ─── SSE ───────────────────────────────────────────────────────────────────
function connectStream() {
  const dot = document.getElementById("streamStatus");
  const label = document.getElementById("streamLabel");
  const feed = document.getElementById("feed");

  const es = new EventSource("/api/stream");
  es.addEventListener("open", () => {
    dot.setAttribute("data-state", "live");
    label.textContent = "live";
  });
  es.addEventListener("invocation", (e) => {
    try {
      const event = JSON.parse(e.data);
      feed.push(event);
    } catch (err) { console.warn("bad event", err); }
  });
  es.addEventListener("error", () => {
    dot.setAttribute("data-state", "error");
    label.textContent = "reconnecting…";
  });
}

// ─── Boot ──────────────────────────────────────────────────────────────────
async function boot() {
  try {
    STATE.catalog = await api.catalog();
    document.getElementById("version").textContent = "v" + STATE.catalog.version;
    document.getElementById("footerLeft").textContent =
      `${STATE.catalog.stats.total_items} items · ${STATE.catalog.version}`;
  } catch (e) {
    document.getElementById("footerLeft").textContent = "catalog load failed: " + e.message;
  }

  try {
    STATE.audit = await api.audit();
    const total = STATE.audit.total || 0;
    document.getElementById("footerRight").textContent =
      `audit: ${total} finding${total === 1 ? "" : "s"}`;
  } catch (e) {
    document.getElementById("footerRight").textContent = "audit unavailable";
  }

  api.bench().then(d => { STATE.bench = d; if (!STATE.selected) document.getElementById("detail").renderHome(); });
  api.cognitiveHealth().then(d => { STATE.cognitive = d; if (!STATE.selected) document.getElementById("detail").renderHome(); });

  document.getElementById("stats").render();
  document.getElementById("tree").render();

  // Restore selection from URL
  const params = new URLSearchParams(location.search);
  if (params.get("kind") && params.get("name")) {
    selectEntity(params.get("kind"), params.get("name"));
  } else {
    document.getElementById("detail").renderHome();
  }

  connectStream();

  // Search
  const search = document.getElementById("search");
  search.addEventListener("input", () => {
    STATE.searchQuery = search.value;
    document.getElementById("tree").render();
  });

  // Cmd-K to focus search
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      search.focus();
      search.select();
    }
    if (e.key === "Escape" && document.activeElement === search) {
      search.value = "";
      STATE.searchQuery = "";
      document.getElementById("tree").render();
      search.blur();
    }
  });

  // Refresh
  document.getElementById("refreshBtn").addEventListener("click", async () => {
    STATE.catalog = await api.catalog();
    STATE.audit = await api.audit();
    document.getElementById("stats").render();
    document.getElementById("tree").render();
    if (STATE.selected) document.getElementById("detail").render();
    else document.getElementById("detail").renderHome();
  });

  // Back button
  window.addEventListener("popstate", () => {
    const p = new URLSearchParams(location.search);
    if (p.get("kind") && p.get("name")) selectEntity(p.get("kind"), p.get("name"));
    else { STATE.selected = null; document.getElementById("detail").renderHome(); }
  });
}

boot();
