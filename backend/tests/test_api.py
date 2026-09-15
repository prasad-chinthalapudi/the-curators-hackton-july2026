from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    assert client.get("/api/health").json()["status"] == "healthy"

def test_search():
    response = client.post("/api/search", json={"query": "healthcare", "page": 1, "page_size": 10})
    assert response.status_code == 200
    assert response.json()["total_documents"] >= 5

def test_search_filtering():
    body = {"query": "", "filters": {"file_types": ["pdf"], "industries": ["Healthcare"]}}
    docs = client.post("/api/search", json=body).json()["documents"]
    assert docs and all(d["file_type"] == "pdf" and d["industry"] == "Healthcare" for d in docs)

def test_document_404():
    assert client.get("/api/documents/missing").status_code == 404

def test_readiness():
    data = client.post("/api/one-pagers/readiness", json={"document_ids": ["doc_001", "doc_002"]}).json()
    assert data["selected_document_count"] == 2 and "coverage" in data

def test_generate_and_get():
    response = client.post("/api/one-pagers", json={"document_ids": ["doc_001"], "title": None})
    assert response.status_code == 201
    assert client.get(f"/api/one-pagers/{response.json()['one_pager_id']}").status_code == 200
    pdf = client.get(f"/api/one-pagers/{response.json()['one_pager_id']}/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF-")

def test_one_pager_pdf_404():
    assert client.get("/api/one-pagers/missing/pdf").status_code == 404

def test_knowledge_save():
    response = client.post("/api/knowledge", json={"question":"Who led delivery?","answer":"Placeholder Lead","related_document_ids":["doc_001"],"contributor":"Tester"})
    assert response.status_code == 201 and response.json()["knowledge_id"]
