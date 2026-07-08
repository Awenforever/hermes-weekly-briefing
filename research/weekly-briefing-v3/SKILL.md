---
name: weekly-briefing-v3
description: Use when running or maintaining the unified academic weekly briefing system: paper discovery, quality filtering, deep analysis, report writing, Typst PDF rendering, email delivery, archive updates, maintenance, recovery, and cleanup.
version: 3.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags:
      - research
      - weekly-briefing
      - academic-papers
      - typst
      - email-delivery
      - operations
    related_skills:
      - research-profile-engine
      - research-profile-evolution
      - arxiv
---

# Weekly Briefing v3

## Overview

`weekly-briefing-v3` is the single self-contained skill for the academic research weekly briefing. It owns discovery, quality filtering, analysis, report writing, PDF rendering, email delivery, persistence, maintenance, and recovery.

The skill bundles all runtime scripts in `scripts/`, all user-editable templates in `templates/`, and detailed specifications in `references/`. Treat this file as the operating guide and load the relevant reference only when deeper detail is needed:

- `references/quality-spec.md` — venue tiers, 6-factor scoring, anti-bias, paper types, relation graph, "论文与我" tags, 28-step flow.
- `references/render-spec.md` — Typst template, PDF fallback, verification, agently-cli delivery, personalization.
- `references/ops-runbook.md` — setup, health checks, archive lifecycle, cleanup, exports, recovery, known pitfalls.

All persistent data paths must resolve from `config.json` `paths.data_dir`. In shell examples use `$DATA_DIR`; do not hardcode a data root. A typical data tree is:

```text
$DATA_DIR/
├── config.json
├── venues.json
├── papers/
│   ├── candidates/
│   ├── archive.json
│   ├── dedup.json
│   ├── taxonomy.json
│   └── relations.json
├── reports/
├── profile/
├── logs/
├── exports/
└── indices/quarterly/
```

## When to Use

Use this skill when asked to:

- Run the weekly academic briefing manually or through cron.
- Discover papers with arXiv API and Crossref, then select a high-value weekly set.
- Apply venue grading, 6-factor scoring, anti-bias constraints, paper classification, and relation graph updates.
- Generate the report, render PDF, and send email with attachment.
- Initialize or audit `$DATA_DIR`, recover archive entries, clean old candidates, export BibTeX or Obsidian notes, or troubleshoot the briefing system.

Do not use generic web search as the primary paper discovery engine. Direct APIs are preferred; web search is for author/team research, fallback enrichment, and anomaly checks.

## Architecture

The weekly briefing is a seven-phase pipeline.

```text
             config.json, venues.json, profile/current.json, topic_feedback
                                      |
                                      v
+------------------------------ Phase 1 ------------------------------+
| Discovery: arXiv API + Crossref -> normalized paper candidates       |
| Output: $DATA_DIR/papers/candidates/{week}_selected.json            |
+----------------------------------+----------------------------------+
                                   |
                                   v
+------------------------------ Phase 2 ------------------------------+
| Quality Filter: venue grading T1-T4/Reject, 6-factor scoring,        |
| anti-bias constraints, dedup against archive/dedup                   |
+----------------------------------+----------------------------------+
                                   |
                                   v
+------------------------------ Phase 3 ------------------------------+
| Deep Analysis: author research, team background, paper classification|
| method/dataset/survey/theory/application, relation graph checks      |
+----------------------------------+----------------------------------+
                                   |
                                   v
+------------------------------ Phase 4 ------------------------------+
| Selection: 3 core papers + 1 cross-domain paper + 1 explore paper    |
| with diversity and previous-week overlap constraints                 |
+----------------------------------+----------------------------------+
                                   |
                                   v
+------------------------------ Phase 5 ------------------------------+
| Report Writing: adaptive templates by paper type, "论文与我" tags,   |
| cross-paper synthesis, timeline, next-week watch list                |
+----------------------------------+----------------------------------+
                                   |
                                   v
+------------------------------ Phase 6 ------------------------------+
| Render & Deliver: Typst -> PDF -> agently-cli email; fallback to     |
| WeasyPrint, fpdf2, or markdown-only when needed                      |
+----------------------------------+----------------------------------+
                                   |
                                   v
+------------------------------ Phase 7 ------------------------------+
| Persist & Cleanup: archive, dedup, taxonomy, relations, receipts,    |
| candidate pruning, PDF retention, health logs                        |
+---------------------------------------------------------------------+
```

Key bundled scripts:

| Script | Purpose |
|--------|---------|
| `scripts/run_weekly_e2e.py` | Main weekly runner for discovery, report artifacts, PDF, email, manifest updates. |
| `scripts/setup.py` | First-time data directory initialization. |
| `scripts/health_check.py` | Dependency and data health checks. |
| `scripts/daily_maintenance.py` | Candidate cleanup, archive review suggestions, relation checks, logs. |
| `scripts/recover_archive.py` | Archive recovery from recovery snapshots, backups, and report manifests. |

## Full Pipeline

### Phase 0: Configuration and Preflight

Create `$DATA_DIR` and copy templates:

```bash
mkdir -p "$DATA_DIR"/{papers/candidates,reports,profile/daily,profile/weekly,profile/monthly,teams,logs,exports,indices/quarterly}
cp {skill_dir}/templates/config.json.template "$DATA_DIR/config.json"
cp {skill_dir}/templates/venues.json.template "$DATA_DIR/venues.json"
```

Edit `$DATA_DIR/config.json` before a real run:

- `paths.data_dir`: absolute or environment-resolved data directory.
- `user.display_name`, `user.research_identity`, `user.one_sentence_profile`.
- `research.core_keywords`, `research.method_keywords`, `research.cross_domain_interests`.
- `style.signature`, `style.email_subject_prefix`, and email recipient settings used by the runner or command wrapper.

Check dependencies:

```bash
which typst && typst --version
python3 -c "from weasyprint import HTML; import fpdf; print('pdf fallback ok')"
fc-list :lang=zh | head -1
command -v agently-cli
```

### Phase 1: Discovery

Use direct APIs first: arXiv API and Crossref. The runner normalizes titles, authors, abstract, DOI/arXiv IDs, venue hints, dates, links, and source metadata.

```bash
python3 {skill_dir}/scripts/run_weekly_e2e.py \
  --week "$(python3 -c 'import datetime; y,w,_=datetime.date.today().isocalendar(); print(f\"{y}-W{w:02d}\")')" \
  --data-dir "$DATA_DIR" \
  --discovery-only
```

Output should land in `$DATA_DIR/papers/candidates/{week}_selected.json` or the manifest path reported by the runner. If fewer than three viable candidates are found, broaden keywords, reduce overly strict arXiv query terms, and run discovery again. Use web search only to supplement missing metadata or investigate authors and teams.

### Phase 2: Quality Filter

Apply `references/quality-spec.md`:

- Venue grading: T1, T2, T3, T4, Reject.
- 6-factor score: venue 0.30, citation 0.15, relevance 0.25, novelty 0.15, reproducibility 0.10, author/team 0.05.
- Anti-bias: topic feedback bounds, diversity hard constraints, topic drift checks, force-explore slot.
- Dedup: compare DOI, arXiv ID, normalized title, and prior archive IDs in `$DATA_DIR/papers/dedup.json` and `$DATA_DIR/papers/archive.json`.

Do not over-trust venue rank: strong T4 preprints can be selected, and weak or irrelevant T1 papers can be excluded.

### Phase 3: Deep Analysis

For each candidate that survives filtering:

1. Read title, abstract, method claims, experiments, limitations, code/data availability.
2. Research first/senior authors and institution context.
3. Map team background: representative work, high-citation papers, lab focus, recent trajectory.
4. Classify the paper as method, dataset, survey, theory, or application.
5. Add "论文与我" tags: `可借鉴`, `须对比`, `竞争`, `空白`.
6. Check relation graph candidates against `$DATA_DIR/papers/relations.json`: cites, cited_by, extends, contradicts, complements, supersedes.

### Phase 4: Selection

Default weekly selection is five papers:

- 3 core papers tightly aligned with the user's active research.
- 1 cross-domain paper that may transfer concepts or tools.
- 1 explore paper that breaks topic feedback loops.

Respect diversity constraints:

- Maximum overlap with previous week: 2 papers or near-duplicate topics.
- At least one force-explore item when recent weeks are too homogeneous.
- Prefer papers with useful contrast: competing method, new dataset, stronger baseline, or clear negative result.

### Phase 5: Report Writing

Write in Chinese unless `config.json` specifies otherwise. Required sections:

- 本周总体判断, 200-300 Chinese characters.
- 入选论文深度分析, using adaptive templates by paper type.
- 文献定位回顾, including relation to archived papers.
- 跨论文综合, with method tree, comparison table, and trend narrative where useful.
- 投稿时间线, including relevant conference/journal deadlines when discovered.
- 下周关注, but do not automatically feed this section into future search weights.

The report should support research decisions, not merely summarize literature. Each selected paper needs a concrete judgment, evidence, user relevance, replication or comparison action, and remaining risk.

### Phase 6: Render & Deliver

Follow `references/render-spec.md`.

Preferred render path:

```bash
cd "$DATA_DIR/reports/{week}/"
typst compile report.typ report.pdf
ls -lh report.pdf
```

Verification:

- `report.pdf` exists and is usually greater than 50 KB.
- `pdftotext report.pdf - | head` extracts the title.
- `grep -n 'sym\\.' report.typ` returns no matches.
- Chinese text renders with CJK fonts.

Email delivery uses `agently-cli message +send` from inside the report directory because `--body-file` and `--attachment` must be relative paths:

```bash
cd "$DATA_DIR/reports/{week}/"
agently-cli message +send \
  --to "your@email.com" \
  --subject "⚚ 学术研究周报 {week} — {主题}" \
  --body-file email_body.txt \
  --attachment report.pdf
```

If a confirmation token is returned, repeat the send command with `--confirmation-token {token}`. For unattended runs, set `HERMES_WEEKLY_EMAIL_AUTO_CONFIRM=1` only after confirming recipient configuration uses the placeholder-replaced intended address.

### Phase 7: Persist & Cleanup

Update persistent state after artifacts are written:

- `$DATA_DIR/papers/dedup.json`: append identifiers and normalized titles for selected papers.
- `$DATA_DIR/papers/archive.json`: append or update selected paper records, report inclusion, reading status, tags, quality tier.
- `$DATA_DIR/papers/taxonomy.json`: update methods, datasets, tasks, domains, and trend labels.
- `$DATA_DIR/papers/relations.json`: add relation graph edges with evidence and last-checked week.
- `$DATA_DIR/reports/{week}/manifest.json`: record inputs, selected papers, render status, email status, errors, and cleanup decisions.

Cleanup policy:

- Keep candidate files for the most recent 12 weeks.
- Keep PDFs for the most recent 12 reports unless the user requests long-term retention.
- Prune dedup entries older than 26 weeks only when they are not in archive or relation graph.
- Never delete `archive.json`, `taxonomy.json`, or `relations.json` automatically.
- Run cleanup dry-run first and include the deletion list in the manifest or maintenance log.

## Common Pitfalls

- **Hardcoded data root**: all data paths must come from `config.json` `paths.data_dir`, `$DATA_DIR`, or `HERMES_WEEKLY_DATA_DIR`.
- **arXiv zero results**: arXiv `all:"query"` can become too strict with many keywords. Broaden terms and rely on Crossref as a second source before declaring failure.
- **agently-cli JSON parsing**: do not pipe `2>&1` into `json.load()`. Some prompts are emitted on stderr and will corrupt stdout JSON.
- **agently-cli relative files**: `--body-file` and `--attachment` must be relative paths; `cd "$DATA_DIR/reports/{week}"` first.
- **Typst symbol support**: avoid `#sym.*`; use plain text or verified Unicode only.
- **Emoji in PDF/email**: the subject prefix can use configured symbols, but avoid emoji inside PDF body when fallback renderers may use incomplete fonts.
- **Warnings vs failures**: dependency warnings such as Typst missing from PATH should not make maintenance fail unless report generation actually requires Typst and no fallback works.
- **Duplicate cron jobs**: keep exactly one weekly briefing schedule active. Verify with the cron tool before adding a replacement.
- **Unverified deletion**: before deleting any skill, script, archive, backup, or report directory, list contents, verify replacements exist, and commit recoverable changes first.

## Verification Checklist

Before a production run:

- `python3 {skill_dir}/scripts/health_check.py` completes or reports only understood warnings.
- `$DATA_DIR/config.json` and `$DATA_DIR/venues.json` exist and contain no placeholder values needed for this run.
- `$DATA_DIR/papers/archive.json`, `dedup.json`, `taxonomy.json`, and `relations.json` exist or setup has initialized them.
- `typst`, CJK fonts, WeasyPrint, fpdf2, `pdftotext`, and `agently-cli` are available or fallback behavior is explicit.

After discovery:

- Candidate JSON exists and is readable.
- Candidate count is sufficient or fallback search was attempted.
- No selected paper duplicates existing DOI, arXiv ID, or normalized title.

After analysis and writing:

- Each selected paper has venue tier, 6-factor score, type classification, relation graph judgment, and "论文与我" tag.
- The final set follows 3 core + 1 cross-domain + 1 explore unless the manifest explains a deviation.
- The report includes overall judgment, deep analysis, historical positioning, synthesis, timeline, and next-week watch list.

After rendering and delivery:

- `report.typ`, `report.pdf`, `email_body.txt`, `manifest.json`, and `delivery_receipt.json` exist.
- PDF size, text extraction, CJK rendering, and absence of `#sym.*` are verified.
- Email command used relative file paths and confirmation was handled or clearly recorded.

After persistence:

- `archive.json`, `dedup.json`, `taxonomy.json`, and `relations.json` are updated consistently.
- Cleanup dry-run or execution log is saved under `$DATA_DIR/logs/`.
- Any persistent repository changes are committed before further destructive operations.
