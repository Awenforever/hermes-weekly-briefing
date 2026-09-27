# Changelog

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
