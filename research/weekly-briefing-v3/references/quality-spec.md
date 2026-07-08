# Quality Specification

This reference defines the quality system for weekly paper discovery, scoring, analysis, selection, and relation tracking. Use it during discovery review, deep analysis, and final selection.

## Table of Contents

- Venue Quality Grading
- 6-Factor Scoring
- Anti-Bias Mechanisms
- Paper Classification
- Relation Graph Types
- "论文与我" Tags
- 28-Step Detailed Flow

## Venue Quality Grading

Venue tier is a prior, not a final decision.

| Tier | Meaning | Examples |
|------|---------|----------|
| T1 | CCF-A, SCI Q1, top conferences or journals | CVPR, ICCV, T-PAMI, IEEE TGRS, RSE |
| T2 | CCF-B, SCI Q2, strong domain venues | IEEE GRSL, Remote Sensing, JSTARS, IGARSS |
| T3 | CCF-C, SCI Q3/Q4, credible but weaker venues | Specialized workshops or regional journals |
| T4 | arXiv or preprint without formal venue | arXiv-only papers, technical reports |
| Reject | Predatory, retracted, unverifiable, or irrelevant | Known predatory journals, fake proceedings |

Rules:

- Reject papers with unreliable venue, fake DOI, retraction, or missing basic bibliographic evidence.
- T4 papers require stronger evidence from novelty, reproducibility, author credibility, or direct relevance.
- A T1 paper can still be excluded when it is off-topic, not actionable, or mostly incremental.
- Maintain venue aliases in `$DATA_DIR/venues.json`; do not bake venue lists into code.

## 6-Factor Scoring

Compute a 0-100 score with weighted factors:

| Factor | Weight | Signals |
|--------|--------|---------|
| Venue | 0.30 | Tier, field fit, formal publication status |
| Citation | 0.15 | Citation count, citation velocity, age-normalized impact |
| Relevance | 0.25 | Match to profile, current projects, methods, datasets, application domain |
| Novelty | 0.15 | New architecture, benchmark, theory, data, or negative/contradictory evidence |
| Reproducibility | 0.10 | Code, data, clear protocol, ablation, compute disclosure |
| Author/team | 0.05 | Track record, institutional fit, prior high-quality work |

Suggested sub-scores:

- Venue: T1=90-100, T2=75-89, T3=55-74, T4=35-85 depending on evidence, Reject=0.
- Citation: normalize by age and field. Do not punish brand-new papers heavily if other evidence is strong.
- Relevance: use `profile/current.json`, `topic_feedback.json`, and active project notes, with manual judgment.
- Novelty: penalize shallow recombination or vague "first" claims without experiments.
- Reproducibility: prefer released code/data or enough detail to reproduce within reasonable effort.
- Author/team: high team score should never rescue an otherwise weak or irrelevant paper.

Selection bands:

- 85-100: strong candidate, likely include if not duplicate.
- 70-84: include when it fills a slot or provides contrast.
- 55-69: keep as backup or explore if strategically useful.
- Below 55: normally exclude.

## Anti-Bias Mechanisms

The system must avoid collapsing into repeated topics or overfitting to last week's interests.

- Feedback isolation: "下周关注" is advisory and must not automatically rewrite `topic_feedback.json`.
- Weight bounds: topic feedback weights must stay between 0.3 and 1.3 unless the user explicitly approves a stronger shift.
- Drift detection: if selected topics repeat for 3 consecutive weeks, inject at least one far-neighbor query.
- Diversity hard constraints: max two papers with near-identical task/method overlap in a normal week.
- Force-explore: preserve one exploration slot even when core candidates are strong.
- Venue bias guard: do not let T1/T2 venue score dominate if relevance or reproducibility is weak.
- Citation bias guard: newly posted papers can be valuable despite low citation count.
- Lab familiarity guard: familiar labs must compete on evidence, not name recognition.

## Paper Classification

Classify every selected paper before writing the analysis.

| Type | Signals | Analysis Focus |
|------|---------|----------------|
| Method | New model, algorithm, loss, training recipe, inference scheme | Mechanism, ablation, compute, baseline strength, generalization |
| Dataset | New dataset, benchmark, annotation protocol, evaluation suite | Coverage, label quality, leakage risk, licensing, complementarity |
| Survey | Review, taxonomy, position paper | Taxonomy usefulness, missing areas, date cutoff, bias |
| Theory | Formal proof, mathematical assumptions, bounds | Assumption realism, implication for practice, empirical gap |
| Application | Existing methods moved into a domain or workflow | Domain gap, transfer fidelity, deployment constraints, failure cases |

Adaptive writing:

- Method papers need a "what changed mechanically" section and a replication checklist.
- Dataset papers need a "would I use it" section with access, licensing, and annotation caveats.
- Survey papers need a "taxonomy I can reuse" section and missing-branch critique.
- Theory papers need a "what assumption matters" section.
- Application papers need a "domain transfer risk" section.

## Relation Graph Types

Store relation edges in `$DATA_DIR/papers/relations.json`.

| Type | Meaning |
|------|---------|
| `cites` | New paper explicitly cites an archived paper. |
| `cited_by` | Archived paper cites or is cited by the new paper where direction matters. |
| `extends` | New paper advances the same line of work. |
| `contradicts` | Findings or claims conflict. |
| `complements` | Different angle solves the same problem or fills a missing piece. |
| `supersedes` | New work replaces a prior baseline, usually same team or same benchmark. |

Each edge should include source paper ID, target paper ID, relation type, evidence string, confidence, and last checked week. Revalidate edges older than 26 weeks during maintenance.

## "论文与我" Tags

Use one or more tags per selected paper:

| Tag | Meaning |
|-----|---------|
| `可借鉴` | Methods, evaluation design, data processing, or writing structure can be reused. |
| `须对比` | Should become a baseline, citation, or experiment comparison. |
| `竞争` | Directly overlaps with the user's research direction or target claim. |
| `空白` | Reveals an underexplored gap or opportunity. |

Make the tag actionable. Bad: "可借鉴 because method is good." Good: "可借鉴: their cross-scale ablation can be reused for the planned dataset shift experiment."

## 28-Step Detailed Flow

### Search and Screening

1. Load `$DATA_DIR/config.json`, `$DATA_DIR/venues.json`, profile, archive, dedup, taxonomy, and relations.
2. Validate required files and initialize missing optional files.
3. Read research profile and topic feedback.
4. Generate a search plan from core keywords, method keywords, cross-domain interests, and recent gaps.
5. Query arXiv API and Crossref directly.
6. If direct search is thin, broaden query terms and optionally use web search for supplemental candidates.
7. Normalize candidate metadata: title, authors, venue, date, DOI, arXiv ID, abstract, links, source.
8. Deduplicate by DOI, arXiv ID, normalized title, and archive IDs.

### Quality Filtering

9. Assign venue tier from `$DATA_DIR/venues.json` and known venue aliases.
10. Compute 6-factor weighted score.
11. Check reproducibility: code, data, protocol, ablations, compute.
12. Apply anti-bias constraints and mark forced diversity candidates.
13. Reject unreliable, retracted, predatory, or unverifiable papers.

### Deep Analysis

14. Research authors and teams with web search when needed.
15. Inspect team trajectory, representative work, and competing labs.
16. Classify each paper type.
17. Identify "论文与我" tags.
18. Cross-check relation graph candidates against archived papers.
19. Review the last three weeks for repetition, missed follow-ups, and citation spikes.
20. Detect citation explosions: roughly 15 or more citations per week over the recent window.

### Selection and Synthesis

21. Select 3 core papers.
22. Select 1 cross-domain paper.
23. Select 1 exploration paper.
24. Validate diversity and previous-week overlap constraints.
25. Build cross-paper synthesis: method tree, comparison table, trend narrative.

### Writing, Delivery, Persistence

26. Write the report with adaptive sections by paper type and personalized judgment.
27. Render PDF and deliver email using the render spec.
28. Update manifest, archive, dedup, taxonomy, relations, quarterly indices, and cleanup logs.
