import json
from datetime import date
from uuid import uuid4
from app.config import DATA_DIR
from app.schemas.models import Coverage, Document, SearchRequest

def read_json(name: str):
    with (DATA_DIR / name).open(encoding="utf-8") as file:
        return json.load(file)

def write_json(name: str, value) -> None:
    with (DATA_DIR / name).open("w", encoding="utf-8") as file:
        json.dump(value, file, indent=2)

def documents() -> list[Document]:
    return [Document.model_validate(item) for item in read_json("documents.json")]

def search(request: SearchRequest):
    items = documents()
    words = [word.lower() for word in request.query.split() if len(word) > 2]
    def matches(doc: Document):
        text = " ".join([doc.file_name, doc.summary, doc.industry, *doc.tags, *doc.technologies]).lower()
        f = request.filters
        return (not words or any(w in text for w in words)) and \
            (not f.file_types or doc.file_type in f.file_types) and \
            (not f.technologies or any(t in doc.technologies for t in f.technologies)) and \
            (not f.industries or doc.industry in f.industries) and \
            (f.year_from is None or doc.year >= f.year_from) and (f.year_to is None or doc.year <= f.year_to)
    found = [d for d in items if matches(d)]
    if request.sort_by == "name": found.sort(key=lambda d: d.file_name)
    else: found.sort(key=lambda d: d.match_score, reverse=True)
    start = (request.page - 1) * request.page_size
    tech = sorted({t for d in found for t in d.technologies})
    industries = sorted({d.industry for d in found})
    total = len(found)
    return {
        "query": request.query, "total_documents": total, "page": request.page,
        "page_size": request.page_size, "total_pages": max(1, (total + request.page_size - 1) // request.page_size),
        "understanding": {"summary": "The matching documents describe relevant data, analytics, and AI implementations.",
            "documents_found": total, "related_clusters": min(3, len(industries)), "key_technologies_count": len(tech),
            "common_technologies": tech[:5], "likely_industries": industries, "confidence": 0.94 if total else 0.0},
        "documents": [d.model_dump(mode="json") for d in found[start:start + request.page_size]],
        "facets": {"file_types": sorted({d.file_type for d in items}), "technologies": sorted({t for d in items for t in d.technologies}),
            "industries": sorted({d.industry for d in items}), "years": sorted({d.year for d in items}, reverse=True)}
    }

def readiness(ids: list[str]):
    selected = [d for d in documents() if d.document_id in ids]
    fields = list(Coverage.model_fields)
    coverage = {}
    gaps = []
    labels = {"delivery_team": "Delivery Team", "lessons_learned": "Lessons Learned", "metrics": "Metrics"}
    for field in fields:
        values = [getattr(d.coverage, field) for d in selected]
        status = "available" if values and all(v == "available" for v in values) else ("partial" if any(v != "missing" for v in values) else "missing")
        coverage[field] = status
        if status != "available":
            gaps.append({"field": field, "label": labels.get(field, field.replace("_", " ").title()), "status": status,
                         "message": f"The selected documents have {status} information for {field.replace('_', ' ')}."})
    return {"status": "ready" if not gaps else "ready_with_gaps", "selected_document_count": len(selected), "coverage": coverage, "gaps": gaps}

def generate(ids: list[str], title: str | None):
    selected = [d for d in documents() if d.document_id in ids]
    if not selected: raise ValueError("No valid documents selected")
    item = {"one_pager_id": f"op_{uuid4().hex[:8]}", "title": title or f"{selected[0].industry} Data & AI Transformation",
        "generated_date": date.today().isoformat(), "case_study_line": f"A consolidated case study from {len(selected)} project documents.",
        "executive_summary": "Blend360 delivered a scalable, governed platform that turns trusted data into decisions.",
        "challenge": "Fragmented platforms and manual processes limited speed, visibility, and trust.",
        "solution": "A cloud-native architecture unified ingestion, engineering, analytics, and governance.",
        "key_features": sorted({t for d in selected for t in d.technologies})[:6],
        "quantified_outcomes": ["35% faster insight delivery", "25% lower operating effort", "99.9% platform availability"],
        "business_value": "The solution improved decision velocity, resilience, and reuse across business teams.",
        "known_gaps": [g["message"] for g in readiness(ids)["gaps"]],
        "sources_used": [{"document_id": d.document_id, "file_name": d.file_name} for d in selected]}
    data = read_json("one_pagers.json"); data.append(item); write_json("one_pagers.json", data)
    return item
