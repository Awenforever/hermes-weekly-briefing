# Installation Evidence — 2026-07-02

Container rebuild install verification. All tools confirmed working.

## Installed Versions

```
Typst:      0.15.0 (3ae52774)  — curl binary install
WeasyPrint: 62.3               — apt-get install weasyprint
fpdf2:      OK                 — apt-get install python3-fpdf
Noto CJK:   20240730+repack1-1 — apt-get install fonts-noto-cjk
```

## Install Commands That Worked

```bash
# Typst
curl -fsSL https://github.com/typst/typst/releases/latest/download/typst-x86_64-unknown-linux-musl.tar.xz -o /tmp/typst.tar.xz
tar -xf /tmp/typst.tar.xz -C /tmp
mv /tmp/typst-x86_64-unknown-linux-musl/typst /usr/local/bin/typst

# WeasyPrint + fpdf2 + fonts
apt-get update -qq
apt-get install -y -qq weasyprint python3-fpdf fonts-noto-cjk
```

## Commands That DID NOT Work

- `pip install weasyprint` — container has no pip module (PEP 668)
- `uv pip install --system weasyprint` — blocked by PEP 668
- `python3 -m pip install ...` — no pip module

## Fallback Font

When Noto Sans CJK SC is not available, Typst can use:
```typst
#set text(font: ("WenQuanYi Zen Hei", "Noto Color Emoji"), size: 10pt, lang: "zh")
```

## Test PDFs Generated

All three engines produced valid PDFs from the same report:
- Typst: 29,363 bytes
- WeasyPrint: 91,105 bytes
- fpdf2: 13,977 bytes