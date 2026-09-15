# PIH API

FastAPI service with two data modes:

- `mock` uses the local placeholder JSON and requires no external services.
- `chroma` retrieves semantically from a persistent Chroma collection using OpenAI embeddings through LangChain.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Run tests with `python -m pytest -q`. Endpoints are rooted at `/api`; interactive docs are available at `/docs`.

## Chroma pilot ingestion

The first retrieval pilot intentionally indexes only 14 extracted records: four
PPTX, four DOCX, four PDF, and two XLSX files. The reviewed selection is stored
in `app/extracted_data/pilot_manifest.json`.

Copy the example environment file and supply your API key:

```powershell
Copy-Item .env.example .env
```

```text
PIH_DATA_MODE=chroma
OPENAI_API_KEY=your-key
```

Create embeddings and persist the collection:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_pilot.py
```

The ingestion command is the only operation that embeds the pilot corpus. It
fails safely when `OPENAI_API_KEY` is absent. PPTX and PDF chunks preserve
slide/page locations; DOCX and XLSX use 1,200-character chunks with 200
characters of overlap.

Start the API after ingestion:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

To return to the offline placeholder implementation, set:

```text
PIH_DATA_MODE=mock
```

## Document extraction

The reusable extraction module supports `.pptx`, `.docx`, `.pdf`, and `.xlsx`.
It preserves slide, page, table, sheet, and row boundaries where the source
format exposes them. Legacy binary `.doc` files are recorded as structured
errors and should be converted to `.docx` before extraction.

Run it with explicit source and output paths:

```powershell
.\.venv\Scripts\python.exe scripts\extract_documents.py `
  "C:\path\to\project-documents" `
  --output "app\extracted_data\document_index.json"
```

For a deterministic development sample:

```powershell
.\.venv\Scripts\python.exe scripts\extract_documents.py `
  "C:\path\to\project-documents" `
  --output "app\extracted_data\pilot_source.json" `
  --max-files 15
```

The output is written atomically and remains compatible with the PIH ingestion
contract. Extraction does not create embeddings or modify Chroma.

## Grounded chat

`POST /api/chat` retrieves fresh evidence for every message. Requests can carry
the same metadata filters as search, selected document IDs, a conversation ID,
and bounded user/assistant history. The response contains structured citations
with document, slide/page/chunk location, excerpt, and relevance score.

```json
{
  "message": "What business outcomes were achieved?",
  "document_ids": ["source_000004"],
  "filters": {
    "file_types": ["pptx"],
    "technologies": [],
    "industries": [],
    "year_from": null,
    "year_to": null
  },
  "conversation_id": null,
  "history": []
}
```

Retrieval and generation failures produce `503` and `502` respectively rather
than returning a successful placeholder answer. If no chunk meets the relevance
threshold, the service returns a grounded no-answer response without calling the
generation model.
