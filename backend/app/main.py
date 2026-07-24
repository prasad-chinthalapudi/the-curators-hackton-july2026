from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from app.schemas.models import SearchRequest, SelectionRequest, GenerateRequest, KnowledgeRequest
from app.services.store import documents, search, readiness, generate, read_json, write_json
from app.services.pdf_service import build_one_pager_pdf
from app.core.settings import settings

app = FastAPI(title="Project Intelligence Hub API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/api/health")
def health(): return {"status": "healthy", "service": "pih-api", "version": "0.1.0"}

@app.post("/api/search")
def search_documents(request: SearchRequest):
    if settings.data_mode == "chroma":
        from app.retrieval.chroma_search_service import search_chroma
        return search_chroma(request)
    return search(request)

@app.get("/api/documents/{document_id}")
def get_document(document_id: str):
    match = next((d for d in documents() if d.document_id == document_id), None)
    if not match: raise HTTPException(404, "Document not found")
    return match

@app.post("/api/one-pagers/readiness")
def one_pager_readiness(request: SelectionRequest): return readiness(request.document_ids)

@app.post("/api/one-pagers", status_code=201)
def create_one_pager(request: GenerateRequest):
    try: return generate(request.document_ids, request.title)
    except ValueError as error: raise HTTPException(400, str(error)) from error

@app.get("/api/one-pagers/{one_pager_id}")
def get_one_pager(one_pager_id: str):
    item = next((x for x in read_json("one_pagers.json") if x["one_pager_id"] == one_pager_id), None)
    if not item: raise HTTPException(404, "One-pager not found")
    return item

@app.get("/api/one-pagers/{one_pager_id}/pdf")
def download_one_pager_pdf(one_pager_id: str):
    item = next((x for x in read_json("one_pagers.json") if x["one_pager_id"] == one_pager_id), None)
    if not item:
        raise HTTPException(404, "One-pager not found")
    filename = f"{one_pager_id}-one-pager.pdf"
    return Response(
        content=build_one_pager_pdf(item),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@app.post("/api/knowledge", status_code=201)
def save_knowledge(request: KnowledgeRequest):
    data = read_json("knowledge.json")
    item = {"knowledge_id": f"k_{len(data)+1:03}", **request.model_dump()}
    data.append(item); write_json("knowledge.json", data)
    return item
