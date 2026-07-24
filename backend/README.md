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
