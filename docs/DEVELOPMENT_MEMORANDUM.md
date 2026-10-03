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
- feedback add/list/remove/clear is persistent and auditable;
- negative feedback changes ranking while positive/explore feedback can extend
  discovery;
- model-generated or non-user feedback is ignored;
- installation, upgrade, scheduling, mail login, report generation and removal
  preserve profile-owned data on supported platforms.
- PDF readiness proves that a renderer is imported from the plugin-owned
  persistent runtime; a matching package found only in Hermes core is not
  reported as an isolated installation.
