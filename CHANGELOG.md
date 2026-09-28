# Changelog

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
