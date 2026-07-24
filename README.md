# Project Intelligence Hub — RAG Backend (UI integration guide)

A ready-to-run FastAPI service that answers grounded questions over ~830 indexed
project documents and returns rich, citable source metadata for the UI. The data
is **already built** — you only run the server and call the API.

## Setup
```bash
python -m venv .venv && .venv/Scripts/activate      # Windows (use bin/activate on *nix)
pip install -r requirements.txt
echo "OPENAI_API_KEY=sk-..." > .env                 # your key, at the repo root
```

## Run
```bash
uvicorn app.main:app --reload        # serves http://localhost:8000
```
Interactive API docs: http://localhost:8000/docs

## Two backends
Both answer the same way; pick per request via `"backend"`:

| backend | data | metadata returned | use for |
|---|---|---|---|
| `docling` **(recommended for UI)** | `data/embeddings/docling_records.pkl` | full: page/slide #, headings, author, dates, **technologies, industries, year, POC + contact emails**, relevance score | filtering, faceted search, cards |
| `chroma` (default) | `data/chroma/` | `source_ref` string only | simple grounded Q&A |

## Endpoints

### `GET /health`
`{ "ok": true, "model": "gpt-5.x-..." }` — verifies the key can call the model.

### `GET /facets`
Distinct filter values with per-document counts — use to build the filter panel.
```json
{ "doc_types": {"pptx":609,"docx":212,"pdf":6,"xlsx":2},
  "technologies": {"AWS":43,"GenAI":39,"Machine Learning":81, "...":0},
  "industries": {"Banking":516,"Retail":70,"Healthcare":35, "...":0},
  "year_min": 2012, "year_max": 2026, "total_documents": 829 }
```

### `POST /query`
```jsonc
{
  "question": "customer analytics and personalization",
  "backend": "docling",          // "docling" | "chroma" (default)
  "top_k": 6,                     // optional, default 6
  "filters": {                    // optional, docling backend only
    "doc_types":   ["pptx"],
    "technologies":["Machine Learning"],
    "industries":  ["Retail"],
    "year_from": 2024,
    "year_to":   2026
  }
}
```
Filters are **OR within a facet, AND across facets**; `year` is an inclusive range.

Response:
```jsonc
{
  "answer": "…grounded answer with [source_ref] citations…",
  "sources": [
    { "source_ref": "Deck.pptx · slide 93",
      "doc_id": "Deck.pptx", "doc_type": "pptx",
      "page_nos": [93], "headings": ["Case Study"],
      "title": null, "author": "Scott Nuernberger",
      "created": "2024-09-12T15:28:23", "modified": "2026-04-29T20:48:58",
      "year": 2026, "technologies": ["AWS"], "industries": ["Retail"],
      "poc_name": "Jane Doe", "poc_email": null, "contact_emails": [],
      "score": 0.59 }
  ],
  "metadata": { "backend": "docling" },
  "mode": "answer"
}
```
The `chroma` backend returns the same shape but populates only `source_ref`.

## Filter value sets
- **Technology:** Azure, Snowflake, Databricks, ADF, AWS, Power BI, Python, Machine Learning, GenAI
- **Industry:** Healthcare, Retail, Travel, Insurance, Banking, Hospitality
- **Document type:** pptx, docx, pdf, xlsx
- **Year:** 2012–2026

## Layout (shared app)
```
app/
  main.py           # FastAPI: /health, /facets, /query
  schemas.py        # request/response models (QueryRequest, Filters, Source)
  config.py         # env, model resolution, paths, shared prompt
  retrieve_docling.py  # docling backend: search + filters + facets + answer
  rag.py            # chroma backend (LCEL chain); loaded lazily
  ingest.py common.py artifacts.py handlers/   # chroma runtime deps
data/
  embeddings/docling_records.pkl   # docling backend store
  chroma/                          # chroma backend store
requirements.txt · .env.example
```
Build scripts, the source dataset, and other non-shipped material live in
`irrelevant/` (git-ignored) — not needed to run the app.

## Notes
- Every model id has a fallback; `resolve_model()` checks the key's models at startup.
- The `docling` backend loads its pickle once and keeps a normalized matrix resident,
  so each query is a single matmul + one embedding call + one generation call.
- The `docling` path does **not** import the Chroma chain — it only loads when a
  request sets `"backend":"chroma"`.
