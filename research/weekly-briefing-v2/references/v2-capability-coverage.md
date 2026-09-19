# Production capability coverage

## Discovery and selection

- arXiv and Crossref discovery
- canonical DOI/arXiv deduplication
- paper-like hard filtering and relevance scoring
- optional, explicitly enabled profile and user-feedback weighting

## Analysis

- per-paper problem, motivation, method, evidence and limitations
- cross-paper comparison
- OpenAlex-backed author/team enrichment with a local cache
- no inferred biographical or citation claims when source data is absent

## Rendering and delivery

- WeasyPrint HTML/CSS PDF with ReportLab fallback
- CJK fonts and clickable DOI/arXiv links
- method cards, comparison tables and author cards
- email-only delivery with durable local receipts

## Safety invariants

- production delivery requires deep analysis
- generated “next focus” text never changes the research profile
- model-generated observations are not treated as user feedback
- no WeChat chunk or WeChat delivery artifact is produced
