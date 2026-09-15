# Project Intelligence Hub

Local FastAPI + React prototype for searching placeholder project knowledge, reviewing AI-style insights, selecting documents, generating one-pagers, and capturing missing knowledge.

## Run locally

Requires Python 3.11+ and Node.js 20+.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Open http://localhost:5173. API documentation is at http://localhost:8000/docs.

## Verification

```powershell
cd backend
python -m pytest -q
cd ..\frontend
npm run build
```

No authentication, external services, document parsing, vector database, or LLM credentials are required.

## Optional Chroma retrieval pilot

The backend now includes an opt-in LangChain + Chroma retrieval mode for a
14-document pilot corpus covering PPTX, DOCX, PDF, and XLSX. Mock mode remains
the default. See `backend/README.md` and `backend/.env.example` for ingestion
and configuration instructions.
