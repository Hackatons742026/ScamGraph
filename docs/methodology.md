# Methodology

This document describes how ScamGraph turns messy incident folders into
explainable, linkable evidence. Engine linking/clustering details live in
`docs/similarity.md` and `docs/clustering.md`. Ingestion runbook:
`docs/ingestion.md`.

## Ingestion pipeline

Offline only — no network calls in the core path.

```text
discover → parse (isolated) → redact → dedup → extract evidence → persist (Repository)
```

### 1. Discovery

Each top-level folder under `$SCAMGRAPH_DATA_DIR` is one incident. Artifact kind
is detected by extension + light content sniffing (hidden `.har`, `*_files/`
siblings, `manifest.json` bundles, `*.info.json` Ad Library, `strona_N` funnel
folders). Funnel **step index** comes from the folder name; **role** is assigned
later.

### 2. Parsing (defensive)

Each artifact runs in its own try/except with `parse_status`
`ok` / `partial` / `failed`. Parsers:

| Kind | Module | Highlights |
|---|---|---|
| HAR | `intake/har.py` | Ordered requests, 3xx/meta/JS redirects, tracking IDs |
| HTML | `intake/html.py` | Title, text, links, forms, DOM skeleton if ≥5 KB, `*_files/` |
| MHTML | `intake/mhtml.py` | stdlib `email` split → HTML parser |
| Bundle | `intake/bundle.py` | Manifest URL/time + nested DOM/HAR/resources |
| Image | `intake/image.py` + `ocr.py` | Cache copy, optional Polish OCR |
| Video | `video.py` | ~2 s frames @720px, pHash dedup, OCR on kept frames |
| Ad Library | `intake/adlib.py` | Ad ID + advertiser page ID (hashed) |

### 3. Redaction

`redact.py` is the privacy gate. `SCAMGRAPH_SALT` is required (fail loud, no
default). Secret query params and Cookie / Set-Cookie / Authorization values
become `sha256(SALT+value)[:12]` before storage or display. Every extracted URL
is redacted.

### 4. Dedup

Exact duplicates (same content digest) collapse with an observation count.
Same kind + basename with different digests are linked as **variants**, not merged.

### 5. Evidence extraction

Registry in `pipeline/extract/`: HAR / HTML / Ad Library / media extractors emit
tiered evidence (A/B/C + family). Ignore lists mark rows `ignored=true` with a
reason instead of dropping them (CDN IPs, public libs, placeholder phones,
small docs). Per-incident **coverage** lists present/missing artifact kinds.

### 6. Funnel roles (PDF §6.5)

Content rules first: Ad Library/image/video → `ad`; article/quiz+CTA →
`prelander`; price/offer language → `offer`; personal-data forms / order
endpoints → `order`. `strona_N` order is fallback only.

### 7. Persist / classify

- Full import: `python -m backend.pipeline.run --data $SCAMGRAPH_DATA_DIR`
  writes via `Repository` (`incidents`, `artifacts`, `evidence`, `media`, `runs`).
- Classify: `process_input(paths, text, url) -> IncidentBundle` with **no** DB
  writes (used by live API classify).

Target: full NASK sample under **2 minutes** on a laptop; missing OCR/ffmpeg
soft-fails without aborting the run.

## What ingestion does not decide

The pipeline never outputs a fraud verdict or attributes material to persons.
Linking and Campaign Memory (Known / New Candidate / Needs Review) are engine
responsibilities after evidence is stored.
