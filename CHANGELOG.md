# Changelog

## 5.3.0 - 2026-10-09

- Add a dependency lifecycle that compares installed Agently/PDF components with current npm/PyPI stable releases on every guided install or plugin upgrade.
- Update Agently explicitly from npm `latest`, then verify the real send, confirmation-token and OAuth-login command contracts while preserving an existing authenticated workspace.
- Remove artificial upper-version caps from the plugin-owned WeasyPrint and ReportLab runtime, update both to current releases, and require post-update import/render compatibility instead of silently pinning old majors.
- Add `dependencies-status` and `dependencies-update --yes`; known outdated or incompatible dependencies now block readiness with an actionable diagnostic, while an unreachable registry remains an honest unknown rather than a false claim.

## 5.2.0 - 2026-10-09

- Restore model-authored, per-issue salutations and Hermes sign-offs without hardcoding a particular user's identity; configured base names are retained and decorated, while unconfigured installs receive safe Hermes-authored identities.
- Persist the generated letter identity in each immutable report snapshot so rerenders are reproducible.
- Add non-blocking Agently device-login commands that return a clickable authorization URL to terminals and Hermes message channels, with an optional adapter-neutral `MEDIA:` QR artifact.
- Keep authentication ownership explicit: Weekly Briefing creates the authorization artifact, while Hermes platform adapters deliver it.

## 5.1.2 - 2026-10-09

- Route historical snapshot rerenders through the same explicit, legacy and
  default letter-identity resolver as normal weekly generation.

## 5.1.1 - 2026-10-09

- Keep salutation and Hermes sign-off customization in onboarding while making
  fresh installations immediately usable with `你好` and `Hermes` defaults.
- Preserve explicit legacy `user.display_name` and `style.signature` values
  during upgrades instead of replacing them with public defaults.

## 5.1.0 - 2026-10-09

- Split delivery into a concise, reader-facing `email_body.md` and the full
  attached `report.pdf`; never send `report.md` as the email body.
- Build the letter from model-owned editorial rationale and grounded paper
  analysis, with a short reading order and an explicit pointer to the PDF.
- Require an explicitly configured recipient salutation and Hermes sign-off on
  new installs, and guide existing installs to fill both before scheduling.
- Apply the same letter/PDF boundary when rebuilding a report from a snapshot.

## 5.0.1 - 2026-10-07

- Retry transient semantic-selection failures as bounded whole operations while
  preserving the configured Hermes primary-to-fallback model route.
- Never amplify a systemic provider or transport outage into one immediate
  request per candidate; per-paper isolation is reserved for a successful but
  incomplete model response.
- Preserve redacted failure diagnostics and retry provenance so a failed run
  identifies the real route, validation or transport problem without exposing
  credentials.

## 5.0.0 - 2026-10-07

- Move topical relevance and final portfolio selection from lexical Boolean
  gates to a two-stage Hermes model review: per-candidate semantic evaluation,
  followed by global comparative selection and model-ordered reserves.
- Treat keywords and concept groups as research-profile and retrieval evidence
  by default; preserve Boolean admission only as an explicit `strict` mode.
- Keep deterministic rejection for objective integrity, date, deduplication,
  evidence and explicit-exclusion boundaries.
- Fail the weekly run when both primary and fallback model routing cannot make
  a valid selection instead of silently publishing a mechanical keyword list.
- Add an auditable semantic-selection receipt with profile, evaluations,
  portfolio rationale, model provenance and isolated candidate failures.
- Keep the report cover to six reader-facing selection metrics so audit-only
  counters cannot spill into a near-empty second page; normalize lightweight
  Markdown residue in repository abstracts before direct HTML/PDF display.
- Keep each semantic selection-reason card atomic across PDF page boundaries.

## 4.9.0 - 2026-10-05

- Treat missing abstracts and incomplete per-paper analysis as quarantined
  candidate failures, with evidence-based reserve selection instead of aborting
  the complete briefing.
- Fall back from batch analysis to isolated per-paper analysis so one malformed
  record cannot discard healthy papers.
- Commit cross-week dedup history only after confirmed email delivery; dry-runs
  and failed runs no longer consume unseen papers.
- Render each run in an attempt directory and publish successful artifacts with
  the manifest last, preserving the last known-good weekly report.
- Add machine-readable quarantine and analysis-isolation receipts.

## 4.8.0 - 2026-10-04

- adds deterministic Boolean relevance policies with AND-across-concept groups,
  OR-within-synonyms, minimum-any, NOT exclusions, and configurable fields;
- pushes required concept combinations into discovery queries and revalidates
  every candidate after retrieval;
- requires strict concepts to co-occur in one semantic segment and rejects
  oversized, repetitive, code-like, or agent-directed repository payloads
  before any model call;
- adds official API adapters for Europe PMC, CORE, HAL, Zenodo, and DataCite;
- expands guided source selection and adds the official OpenAlex key link.

## 4.7.2 - 2026-10-03

- Treat an empty `timezone: ''` configuration value as absent so Docker's
  standard `TZ` fallback is reached instead of returning an empty timezone.

## 4.7.1 - 2026-10-03

- Recognize the standard container `TZ` value when no Hermes-specific timezone
  is present, while keeping an actually missing timezone as a setup blocker.

## 4.7.0 - 2026-10-03

- Removed developer research topics and examples from the public setup surface.
- Retired unverifiable automatic profile weighting.
- Added explicit, channel-independent feedback commands with an append-only audit trail.
- Made new installations inherit the Hermes profile timezone instead of using an author-specific default.
- Clarified that email is an output channel, not a feedback-ingestion mechanism.
- Require PDF dependencies to exist in the plugin-owned persistent runtime instead of treating packages found in the replaceable Hermes core environment as an isolated installation.
- Keep setup unresolved when no Hermes profile timezone can be inherited, preventing device-local timezone drift.

## 4.6.8 - 2026-09-29

- Make the published configuration template inherit Hermes model routing and
  leave both primary and fallback model selection to the user's Hermes setup.

## 4.6.7 - 2026-09-29

- Decode captured Hermes, Agently, and renderer output explicitly as UTF-8 with
  replacement diagnostics. Windows no longer crashes while reading cron output
  that contains localized or non-ASCII text.

## 4.6.6 - 2026-09-28

- Pass the single, validated Agently CLI path from the plugin entry point into
  the report subprocess. This prevents execution from disagreeing with doctor
  and setup on environments whose global command shims are not in `PATH`.

## 4.6.5 - 2026-09-28

- Discover npm in user-scoped WinGet Node installations where Windows exposes
  `node.exe` as an alias but omits `npm.cmd` from `PATH`.
- Discover Agently command shims beside npm and in the standard Windows roaming
  npm command directory, so a successful installation is immediately usable.

## 4.6.4 - 2026-09-28

- Use Hermes' verified CA bundle when embedded Windows Python has no system CA file, restoring HTTPS academic-source discovery without weakening TLS checks.
- Make renderer diagnostics tolerate optional WeasyPrint native-library banners and correctly recognize the ReportLab fallback in the isolated plugin runtime.

## 4.6.3 - 2026-09-28

- Pin isolated PDF packages to Hermes' active Python interpreter and segregate them by Python ABI and operating system, preventing cross-version native-wheel mismatches.

## 4.6.2 - 2026-09-28

- Keep PDF renderer packages in the plugin's persistent data directory instead of Hermes' core virtual environment, so a normal Hermes upgrade cannot remove them.
- Run and diagnose rendering with that plugin-owned runtime on Linux, Windows, WSL2, and Docker.
- Stop declaring renderer packages as core plugin dependencies; `runtime-install` is the sole owner of the isolated renderer runtime.

## 4.6.1 - 2026-09-28

- Locate the Hermes profile-managed `uv` executable during PDF runtime setup, including native Windows `uv.exe`, so a standard Hermes installation does not incorrectly report that no package manager is available.

## 4.6.0 - 2026-09-28

- Expand first-class discovery to OpenAlex, Semantic Scholar, Crossref, arXiv,
  DBLP and OpenReview, with optional credential-backed Scopus and Google Scholar
  through SerpApi.
- Merge duplicate papers across indexes while retaining provenance and the richest
  available metadata.
- Prefer source breadth only among similarly strong candidates, avoiding both
  single-index domination and low-quality source quotas.
- Derive queries and relevance gates entirely from onboarding configuration;
  public installs no longer inherit the maintainer's production research topic.
- Add live source diagnostics and clear credential guidance without storing keys.
