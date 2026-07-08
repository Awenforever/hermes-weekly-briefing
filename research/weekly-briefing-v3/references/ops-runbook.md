# Operations Runbook

Use this reference for setup, maintenance, recovery, health checks, cleanup, and exports.

## Table of Contents

- Path and Script Conventions
- Initialization Checklist
- Maintenance Scripts
- Archive Lifecycle Management
- Cleanup Policies
- Health Check Items
- BibTeX and Obsidian Export
- Recovery
- Known Pitfalls
- Git and Deletion Rules

## Path and Script Conventions

- Data root: `$DATA_DIR`, normally read from `config.json` `paths.data_dir`.
- Alternate env var accepted by scripts: `HERMES_WEEKLY_DATA_DIR`.
- Skill scripts: `{skill_dir}/scripts/`.
- Logs: `$DATA_DIR/logs/`.

Do not hardcode machine-specific paths in docs, scripts, manifests, cron prompts, or templates.

## Initialization Checklist

1. Choose and export data directory:

```bash
export DATA_DIR="/path/to/weekly-briefing"
```

2. Create directories:

```bash
mkdir -p "$DATA_DIR"/{papers/candidates,reports,profile/daily,profile/weekly,profile/monthly,teams,logs,exports,indices/quarterly}
```

3. Copy templates:

```bash
cp {skill_dir}/templates/config.json.template "$DATA_DIR/config.json"
cp {skill_dir}/templates/venues.json.template "$DATA_DIR/venues.json"
```

4. Fill required config placeholders:

- User name, identity, research direction.
- Core keywords, method keywords, cross-domain interests.
- Signature and subject prefix.
- Data directory.

5. Check dependencies:

```bash
which typst && typst --version
python3 -c "from weasyprint import HTML; import fpdf; print('ok')"
fc-list :lang=zh | head -1
which pdftotext
command -v agently-cli
agently-cli +me
```

6. Initialize or validate JSON files:

- `$DATA_DIR/papers/archive.json`
- `$DATA_DIR/papers/dedup.json`
- `$DATA_DIR/papers/taxonomy.json`
- `$DATA_DIR/papers/relations.json`

## Maintenance Scripts

| Script | Trigger | Purpose |
|--------|---------|---------|
| `setup.py` | First install | Create directory skeleton and seed files. |
| `health_check.py` | Manual or troubleshooting | Check dependencies and data integrity. |
| `daily_maintenance.py` | Daily cron or manual | Candidate pruning, archive review warnings, relation aging, logs. |
| `recover_archive.py` | Manual emergency | Rebuild archive entries from backups and manifests. |
| `run_weekly_e2e.py` | Weekly cron or manual | Main briefing pipeline. |

Examples:

```bash
DATA_DIR="$DATA_DIR" python3 {skill_dir}/scripts/health_check.py
DATA_DIR="$DATA_DIR" python3 {skill_dir}/scripts/daily_maintenance.py
DATA_DIR="$DATA_DIR" python3 {skill_dir}/scripts/recover_archive.py --dry-run --verbose
```

## Archive Lifecycle Management

Store archive records in `$DATA_DIR/papers/archive.json`.

Suggested schema:

```json
{
  "papers": [
    {
      "archive_id": "uuid",
      "title": "...",
      "canonical_id": "doi or arxiv id",
      "first_seen_week": "2026-W27",
      "last_checked_week": "2026-W30",
      "included_in_reports": ["2026-W27"],
      "reading_status": "unread",
      "notes": "",
      "tags": ["must-cite", "baseline", "competitor", "reference"],
      "quality_tier": "T1",
      "superseded_by": null,
      "retracted": false
    }
  ]
}
```

Review process:

1. Superseded detection: inspect `relations.json` for `supersedes` edges.
2. Retraction detection: search for retraction, withdrawal, expression of concern.
3. Publication status changes: T4 preprints may become formally published.
4. Citation velocity: roughly 15 or more citations per week over recent weeks means `trending`.
5. Reading status aging: flag important papers left unread for more than four weeks.

## Cleanup Policies

| Data | Policy |
|------|--------|
| `$DATA_DIR/papers/candidates/*.json` | Keep most recent 12 weeks. |
| `$DATA_DIR/reports/*/report.pdf` | Keep most recent 12 reports unless user wants permanent retention. |
| `$DATA_DIR/papers/dedup.json` | Remove entries older than 26 weeks only if not referenced elsewhere. |
| `$DATA_DIR/papers/archive.json` | Permanent; never auto-delete. |
| `$DATA_DIR/papers/taxonomy.json` | Permanent; update cautiously. |
| `$DATA_DIR/papers/relations.json` | Revalidate edges older than 26 weeks; do not blindly delete. |
| `$DATA_DIR/logs/*` | Rotate if large, preserve failure logs. |

Always run cleanup as dry-run first and write the deletion plan into a log or manifest.

## Health Check Items

System:

- Typst available through PATH or known install location.
- WeasyPrint import works.
- fpdf2 import works.
- CJK fonts are installed.
- `pdftotext` available for verification.
- `agently-cli` installed and OAuth token valid.

Data:

- Required JSON files exist and parse.
- `archive.json` records have stable IDs, titles, reading statuses, and first seen week.
- `dedup.json` has DOI/arXiv/title keys where available.
- `relations.json` has valid source/target IDs.
- Candidate files do not exceed retention policy without a cleanup log.
- Latest report manifest is internally consistent.

## BibTeX and Obsidian Export

BibTeX target:

```text
$DATA_DIR/exports/bibliography.bib
```

Include archived papers with enough metadata: title, authors, year, venue, DOI, arXiv, URL, and tags where possible.

Obsidian target:

```text
$DATA_DIR/exports/obsidian/{paper_id}.md
```

Suggested frontmatter:

```yaml
---
title: "Paper title"
year: 2026
venue: "Venue"
quality_tier: "T1"
tags: ["baseline", "competitor"]
canonical_id: "..."
---
```

Body should include summary, "论文与我" judgment, relations, replication notes, and report inclusion links.

## Recovery

Use `recover_archive.py` to rebuild missing archive entries from:

1. `$DATA_DIR/recovery/**/*.bak`
2. `$DATA_DIR/backups/**/archive.json`
3. `$DATA_DIR/reports/*/manifest.json`

Run dry-run first:

```bash
DATA_DIR="$DATA_DIR" python3 {skill_dir}/scripts/recover_archive.py --dry-run --verbose
```

Then run without dry-run only after reviewing the proposed additions:

```bash
DATA_DIR="$DATA_DIR" python3 {skill_dir}/scripts/recover_archive.py --verbose
```

Recovery should never overwrite a richer existing archive record with a poorer recovered record. Prefer merging missing fields and preserving manual notes.

## Known Pitfalls

### Typst PATH Detection

Do not use `os.path.exists("typst")` to check command availability. That only checks for a file named `typst` in the current working directory. Use:

```python
shutil.which("typst")
```

or check an explicit install path if the environment documents one.

### Maintenance Exit Logic

Maintenance should exit non-zero only for actual data corruption, missing critical files, failed writes, or other critical errors. Warnings such as missing optional renderer should be logged but should not fail daily maintenance.

### Cron Manual Runs

If a cron management tool has an `action=run` mode, verify it actually executes in the current environment. Manual weekly runs should call the pipeline directly instead of assuming cron fire-on-demand works.

### agently-cli Streams

Do not merge stderr into stdout when parsing JSON. Capture stderr separately or discard it for JSON parse commands.

### agently-cli File Arguments

`--body-file` and `--attachment` must be relative paths. Change directory into `$DATA_DIR/reports/{week}/` before sending.

## Git and Deletion Rules

Persistent repositories can include the skill repository, the weekly data repository, and local Hermes configuration. Before destructive operations:

1. Check status.
2. Preserve or commit current work.
3. List files to be deleted.
4. Verify replacement scripts and references exist.
5. Verify no cron job points at the soon-to-be-deleted path.
6. Delete only after the above checks pass.

For skill consolidation specifically, every script from retired directories must exist in the new skill's `scripts/` directory before deleting old directories.
