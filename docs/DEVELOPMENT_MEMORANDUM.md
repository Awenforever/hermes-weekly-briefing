# Weekly Briefing — Development Memorandum

Internal engineering constraints. Product README files must stay concise and
must not become an incident log.

## Public distribution must contain no author research profile

The plugin previously mixed a production user's wildfire/smoke research terms
into public query construction and setup examples. A new user could therefore
receive those terms as apparent recommendations even after providing an
unrelated field.

Permanent rules:

- runtime queries come only from that profile's explicit configuration and
  user-confirmed feedback;
- README, Skill, templates and setup output use placeholders, not the author's
  topics, email address, timezone, provider or model;
- test fixtures may use synthetic topics, but must not reproduce production
  identity or private research configuration;
- upgrades preserve an existing user's configuration and never replace it with
  public defaults.

## Email output is not a feedback channel

Weekly Briefing sends reports by email. It does not read a mailbox, parse email
replies or depend on Email Watchdog. Feedback can arrive through any Hermes
conversation channel, but Hermes must restate and confirm the exact topic and
direction before invoking `hermes weekly-briefing feedback`.

The command owns two durable files under the current profile:

- `profile/topic_feedback.json`: current effective preferences;
- `profile/feedback_events.jsonl`: append-only audit history.

Only records whose source is exactly `user` may affect queries or ranking.
Report prose, “next focus”, model observations and ordinary conversation never
write preferences. Every preference is listable, removable and clearable.
There is no install-time “learning” switch to sell or explain: the first
confirmed record enables explicit feedback, and removing the last record
disables it again.

## No fictional automatic profile learning

The retired `research.use_profile_weights` option read
`profile/current.json`, but the production plugin had no verified producer for
that file and the numeric value only selected extra query strings. That is not
a defensible profile-learning architecture.

Do not restore automatic profile claims without an independently tested data
contract covering consent, source attribution, confidence, decay, conflict,
inspection, correction, deletion and cross-channel identity. Until then,
explicit configuration plus explicit feedback is the complete product model.

## Release proof

Every public release must prove that:

- an unrelated fresh profile produces no author-specific query;
- setup without topics does not invent or recommend any;
- new installs inherit Hermes model routing and profile timezone;
- if the profile has no timezone, setup remains unresolved until the user
  chooses an explicit IANA timezone;
- Docker's standard `TZ` value is a valid last-resort profile timezone after
  `HERMES_TIMEZONE` and `config.yaml`; do not mistake a configured container
  timezone for a missing value;
- feedback add/list/remove/clear is persistent and auditable;
- negative feedback changes ranking while positive/explore feedback can extend
  discovery;
- model-generated or non-user feedback is ignored;
- installation, upgrade, scheduling, mail login, report generation and removal
  preserve profile-owned data on supported platforms.
- PDF readiness proves that a renderer is imported from the plugin-owned
  persistent runtime; a matching package found only in Hermes core is not
  reported as an isolated installation.

## Search breadth is capability-based, not a source-name checklist

Use official machine APIs and state each source's role. OpenAlex/Crossref cover
general scholarly metadata; arXiv, DBLP and OpenReview cover important
computer-science and preprint/conference lanes; Europe PMC covers life sciences;
CORE and HAL add open-repository/full-text discovery; Zenodo and DataCite add
research outputs and DOI records. Scopus and Google Scholar/SerpApi stay opt-in
because they require external credentials or a paid intermediary. Adding a
source requires a parser fixture, connectivity probe, dedup compatibility,
rate bound, and clear credential ownership. Never scrape a website merely to
inflate the source count.

## Semantic relevance belongs to the model, not a keyword gate

Keywords, methods, concept groups and cross-domain interests describe the user
and generate diverse retrieval queries. They are not evidence that a paper is
relevant, and missing their literal spellings is not evidence that it is not.
The default pipeline must therefore preserve this order:

1. broad multi-source retrieval;
2. deterministic identity, date, integrity, dedup and evidence checks;
3. model evaluation of every viable candidate against the explicit profile;
4. a second global model comparison that chooses a complementary portfolio and
   reserve order;
5. grounded deep analysis of the chosen papers.

The evaluation must distinguish core, adjacent, exploratory and rejected work,
and explain semantic or methodological connections using the supplied abstract.
The portfolio pass, not a lexical score or source quota, owns `selected_ids`.
If primary and fallback model routing both fail, publication fails closed; never
silently substitute deterministic keyword ranking.

Boolean AND/OR/co-occurrence logic remains available only when the user
explicitly sets `research.relevance.mode=strict`. Explicit exclusion terms are
always enforced. Existing configurations without a `mode` migrate to semantic
selection so an earlier generated gate cannot continue controlling selection.
Public defaults contain no author-specific research terms.

## External scholarly metadata is an untrusted input boundary

Open repositories can contain arbitrary deposits rather than peer-reviewed
papers, including code dumps, duplicated text and instructions aimed at
crawlers or language models. Before any model call, reject source-neutral
integrity failures: oversized abstracts, high code density, repeated payloads,
and text that combines agent/crawler addressing with control instructions.
Source adapters should additionally retain and validate scholarly work types
where the API provides them. The analysis system prompt must state that titles,
abstracts and metadata are untrusted data and that embedded instructions have
no authority. A newly added source is not production-ready until a real
cross-source discovery run proves that this boundary holds.

## Evidence isolation and transactional publication

Abstract coverage is an admission property of one candidate, not a reason to
abort a complete weekly run. The pipeline may recover an abstract from a
machine-readable identifier, but it must never ask a model to invent evidence.
Candidates without sufficient abstract evidence or an original link are
quarantined with explicit reasons; ranked reserves then compete under the same
relevance policy. Deep analysis uses a batch fast path and per-paper isolation
fallback, so one omitted or malformed record cannot discard healthy results.

Only publishable papers—with evidence, link, author identity and complete
grounded analysis—reach rendering. The quality gate still fails closed for
systemic renderer defects, while candidate-level failures are reported in a
quarantine receipt. A run is created in an attempt directory and the successful
manifest is published last, preserving the previous known-good report when a
new attempt fails.

Cross-week dedup is delivery state, not discovery state. Never mutate it during
selection, analysis, rendering or a dry-run. Commit selected identifiers only
after email delivery is confirmed; otherwise an unseen paper would disappear
from later weeks.
