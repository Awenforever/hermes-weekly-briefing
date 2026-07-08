# Render and Delivery Specification

Use this reference when turning the weekly report into a PDF and delivering it by email.

## Table of Contents

- Render Strategy
- Typst Template
- Paper Card Macro
- Fallback Ladder
- PDF Verification
- Email Delivery
- Personalization Rules
- agently-cli Pitfalls

## Render Strategy

The render target is a polished academic PDF with a concise email wrapper. The preferred path is:

```text
report.md / structured report data -> report.typ -> report.pdf -> agently-cli email
```

Fallback path:

```text
Typst -> WeasyPrint -> fpdf2 -> markdown-only email
```

Keep report assets inside `$DATA_DIR/reports/{week}/`:

- `report.md`
- `report.typ`
- `report.pdf`
- `email_body.txt`
- `report_meta.json`
- `delivery_receipt.json`
- `manifest.json`

## Typst Template

Use restrained academic styling: strong title bar, clear paper cards, readable CJK fonts, table rules, and compact badges.

```typst
#let primary = rgb("#1a365d")
#let accent = rgb("#2b6cb0")
#let light-bg = rgb("#f7fafc")
#let border = rgb("#e2e8f0")
#let muted = rgb("#4a5568")
#let tag-can-use = rgb("#3182ce")
#let tag-compare = rgb("#dd6b20")
#let tag-compete = rgb("#e53e3e")
#let tag-gap = rgb("#38a169")

#set page(paper: "a4", margin: (top: 2.5cm, bottom: 2cm, left: 2.2cm, right: 2.2cm))
#set text(font: ("Noto Sans CJK SC", "Noto Serif CJK SC"), size: 10pt, lang: "zh")
#set heading(numbering: none)

#let title-block(week, subtitle, generated) = {
  block(fill: primary, inset: (x: 0pt, y: 20pt), width: 100%, radius: 4pt)[
    #align(center)[
      #text(size: 22pt, weight: "bold", fill: white)[Academic Research Weekly Briefing]
      #v(0.3cm)
      #text(size: 14pt, fill: rgb("#bee3f8"))[#week]
      #v(0.2cm)
      #text(size: 9pt, fill: rgb("#90cdf4"))[#subtitle · #generated]
    ]
  ]
}

#show heading.where(level: 1): it => block(above: 12pt, below: 6pt)[
  #text(size: 15pt, weight: "bold", fill: primary)[#it.body]
  #line(length: 100%, stroke: 0.7pt + border)
]

#show heading.where(level: 2): it => block(above: 8pt, below: 4pt)[
  #text(size: 12pt, weight: "bold", fill: accent)[#it.body]
]
```

Rules:

- Do not use `#sym.*`; container fonts and Typst versions may not support expected symbols.
- Avoid Unicode emoji in the report body. Prefer text labels or colored badges.
- Use explicit styles; do not depend on renderer defaults.
- Keep color use meaningful: title, section lines, tags, table headers.

## Paper Card Macro

```typst
#let tag(label, color) = box(
  fill: color.lighten(80%),
  stroke: 0.4pt + color,
  radius: 2pt,
  inset: (x: 5pt, y: 2pt),
  text(size: 7.5pt, fill: color, weight: "bold")[#label],
)

#let paper-card(title, authors, venue, year, tags, body) = {
  block(fill: light-bg, inset: 14pt, radius: 3pt, stroke: 0.5pt + border, above: 8pt, below: 8pt)[
    #text(size: 11pt, weight: "bold", fill: primary)[#title]
    #v(0.2cm)
    #text(size: 8.5pt, fill: muted)[#authors · #venue · #year]
    #v(0.25cm)
    #tags
    #v(0.35cm)
    #body
  ]
}
```

Suggested tag colors:

- `可借鉴`: `tag-can-use`
- `须对比`: `tag-compare`
- `竞争`: `tag-compete`
- `空白`: `tag-gap`

## Fallback Ladder

### Level 1: Typst

```bash
cd "$DATA_DIR/reports/{week}/"
typst compile report.typ report.pdf
```

Use when Typst is available and CJK fonts are installed.

### Level 2: WeasyPrint

Use when Typst fails but HTML/CSS conversion is available. Requirements:

- Explicit CSS font stack with CJK fonts.
- No default unordered list bullets; define list markers explicitly.
- Embed or link only local assets under `$DATA_DIR/reports/{week}/`.

### Level 3: fpdf2

Use for minimal PDF output when both Typst and WeasyPrint fail. Requirements:

- Register CJK font if available.
- Preserve title, selected papers, key judgments, and links.
- Record degraded render status in `manifest.json`.

### Markdown-only

If all PDF generation fails, send `email_body.txt` plus the markdown report body and record the failure in `delivery_receipt.json`. Do not fabricate a PDF success.

## PDF Verification

Run these checks before email delivery:

```bash
test -s report.pdf
ls -lh report.pdf
pdftotext report.pdf - | head -20
grep -n 'sym\\.' report.typ || true
```

Criteria:

- `report.pdf` exists and is normally greater than 50 KB for a full weekly report.
- `pdftotext` extracts the report title or major headings.
- No `#sym.*` remains in Typst source.
- Chinese characters are visible when sampled or inspected.
- Manifest records renderer, fallback level, command return code, and artifact paths.

## Email Delivery

Use `agently-cli` after verifying it is installed and authenticated:

```bash
command -v agently-cli
agently-cli +me
```

Send from the report directory. `--body-file` and `--attachment` must be relative paths.

```bash
cd "$DATA_DIR/reports/{week}/"
agently-cli message +send \
  --to "your@email.com" \
  --subject "⚚ 学术研究周报 {week} — {主题}" \
  --body-file email_body.txt \
  --attachment report.pdf
```

If the response indicates confirmation is required, repeat the same command with:

```bash
--confirmation-token "{token}"
```

When `HERMES_WEEKLY_EMAIL_AUTO_CONFIRM=1`, the runner may confirm automatically. Only use this in production after the recipient is configured correctly.

## Personalization Rules

Read personalization from `$DATA_DIR/config.json`:

- `user.display_name`
- `user.research_identity`
- `style.role`
- `style.signature`
- `style.allow_variable_mood`
- `style.email_subject_prefix`

Email body:

- Start with a short Chinese greeting, one or two sentences.
- Keep tone personal but concise.
- Mention the strongest weekly theme and attach the PDF.
- Include a brief note if delivery used a degraded PDF fallback.
- Sign with configured signature.

Subject:

```text
{prefix} 学术研究周报 {week} — {one-line theme}
```

## agently-cli Pitfalls

### stderr Mixed into JSON

Some `agently-cli` tips are emitted on stderr. Do not merge stderr into stdout when parsing JSON:

```bash
# Bad for JSON parsing
agently-cli message +list --limit 1 2>&1 | python3 -c "import json,sys; json.load(sys.stdin)"

# Good
agently-cli message +list --limit 1 2>/dev/null | python3 -c "import json,sys; json.load(sys.stdin)"
```

If both streams are needed, capture them separately:

```bash
agently-cli message +send ... > /tmp/stdout.txt 2> /tmp/stderr.txt
```

### Relative Body and Attachment Paths

This fails:

```bash
agently-cli message +send --body-file "$DATA_DIR/reports/{week}/email_body.txt"
```

This works:

```bash
cd "$DATA_DIR/reports/{week}/"
agently-cli message +send --to "your@email.com" --subject "..." --body-file email_body.txt --attachment report.pdf
```

### Authentication Expiry

If `agently-cli +me` fails, renew OAuth:

```bash
agently-cli auth login
```
