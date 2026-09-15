# Codex Build Instructions: PIH FastAPI + React Frontend

## Objective

Build a working local prototype for **Project Intelligence Hub (PIH)** using:

- Backend: FastAPI + Python
- Frontend: React + TypeScript + Vite
- Styling: Tailwind CSS
- Data: Placeholder JSON data only
- API calls: Real frontend-to-backend integration
- No authentication
- No vector database
- No document parsing
- No LLM calls
- No production deployment

The goal is to create the complete user interface and API contract using placeholder values so the real document search and AI logic can be added later.

## Product Flow

The user should be able to:

1. Enter a natural-language requirement.
2. Apply filters.
3. Search documents.
4. View AI-style summary cards.
5. View matching documents in a table.
6. Select documents.
7. Generate a placeholder one-pager.
8. View knowledge coverage.
9. View an AI assistant panel.
10. Add missing knowledge through a modal.

## Required Stack

### Backend

- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic v2
- pytest
- httpx
- python-dotenv

### Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- React Router
- TanStack Query
- TanStack Table
- Axios
- Lucide React

Do not use Next.js, Redux, SQLAlchemy, Redis, Celery, a vector database, or external AI services.

## Project Structure

```text
pih/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/routes/
│   │   │   ├── health.py
│   │   │   ├── search.py
│   │   │   ├── documents.py
│   │   │   ├── one_pagers.py
│   │   │   └── knowledge.py
│   │   ├── schemas/
│   │   │   ├── search.py
│   │   │   ├── document.py
│   │   │   ├── one_pager.py
│   │   │   └── knowledge.py
│   │   ├── services/
│   │   │   ├── mock_search_service.py
│   │   │   ├── mock_document_service.py
│   │   │   ├── mock_one_pager_service.py
│   │   │   └── mock_knowledge_service.py
│   │   └── data/
│   │       ├── documents.json
│   │       ├── one_pagers.json
│   │       └── knowledge.json
│   ├── tests/
│   ├── requirements.txt
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── pages/
│   │   ├── types/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── README.md
├── README.md
└── .gitignore
```

## Backend Requirements

### CORS

Allow:

```python
allow_origins=["http://localhost:5173"]
```

### Health Endpoint

```http
GET /api/health
```

Response:

```json
{
  "status": "healthy",
  "service": "pih-api",
  "version": "0.1.0"
}
```

### Search Endpoint

```http
POST /api/search
```

Request:

```json
{
  "query": "Need healthcare projects using Snowflake and Azure Databricks",
  "filters": {
    "file_types": ["pptx", "pdf", "docx"],
    "technologies": ["Azure", "Snowflake"],
    "industries": ["Healthcare"],
    "year_from": 2020,
    "year_to": 2026
  },
  "page": 1,
  "page_size": 10,
  "sort_by": "relevance"
}
```

The mock service must:

1. Read `documents.json`.
2. Match the query against file name, summary, tags, technologies, and industry.
3. Apply filters.
4. Paginate results.
5. Return fixed AI understanding values based on the matching set.
6. Return available filter values and counts.

Response shape:

```json
{
  "query": "Need healthcare projects using Snowflake and Azure Databricks",
  "total_documents": 23,
  "page": 1,
  "page_size": 10,
  "total_pages": 3,
  "understanding": {
    "summary": "The matching documents mainly describe healthcare data warehouse and analytics implementations.",
    "documents_found": 23,
    "related_clusters": 3,
    "key_technologies_count": 4,
    "common_technologies": ["Azure", "Snowflake", "Databricks", "ADF"],
    "likely_industries": ["Healthcare"],
    "confidence": 0.94
  },
  "documents": [],
  "facets": {
    "file_types": [],
    "technologies": [],
    "industries": [],
    "years": []
  }
}
```

### Document Model

```json
{
  "document_id": "doc_001",
  "file_name": "Healthcare_EDW_Overview.pptx",
  "file_type": "pptx",
  "match_score": 0.98,
  "summary": "High-level overview of a healthcare enterprise data warehouse implementation.",
  "tags": ["Architecture", "Overview", "Executive"],
  "technologies": ["Azure", "Databricks", "ADF"],
  "industry": "Healthcare",
  "year": 2025,
  "added_on": "2025-05-12",
  "source_locations": [
    {
      "location_type": "slide",
      "location_number": 8,
      "excerpt": "Blend360 designed a scalable healthcare data platform..."
    }
  ],
  "coverage": {
    "executive_summary": "available",
    "challenge": "available",
    "solution": "available",
    "technology_stack": "available",
    "business_outcome": "available",
    "metrics": "partial",
    "delivery_team": "missing",
    "lessons_learned": "partial"
  }
}
```

Create at least 25 realistic placeholder documents across PPTX, PDF, and DOCX.

Use technologies such as Azure, Snowflake, Databricks, ADF, AWS, Redshift, Python, Power BI, Machine Learning, and GenAI.

Use industries such as Healthcare, Retail, Travel, Insurance, Banking, and Hospitality.

### Document Details

```http
GET /api/documents/{document_id}
```

Return one full document object. Return HTTP 404 when not found.

### One-Pager Readiness

```http
POST /api/one-pagers/readiness
```

Request:

```json
{
  "document_ids": ["doc_001", "doc_002", "doc_003"]
}
```

Response:

```json
{
  "status": "ready_with_gaps",
  "selected_document_count": 3,
  "coverage": {
    "executive_summary": "available",
    "challenge": "available",
    "solution": "available",
    "technology_stack": "available",
    "business_outcome": "available",
    "metrics": "partial",
    "delivery_team": "missing",
    "lessons_learned": "partial"
  },
  "gaps": [
    {
      "field": "delivery_team",
      "label": "Delivery Team",
      "status": "missing",
      "message": "The selected documents do not identify the complete delivery team."
    }
  ]
}
```

### Generate One-Pager

```http
POST /api/one-pagers
```

Request:

```json
{
  "document_ids": ["doc_001", "doc_002", "doc_003"],
  "title": null
}
```

Return a placeholder one-pager with:

- Title
- Generated date
- Case study line
- Executive Summary
- The Challenge
- Our Solution
- Key Features
- Quantified Outcomes
- Business Value
- Known Gaps / Caveats
- Sources Used

Store it in `one_pagers.json` or in memory.

### Get One-Pager

```http
GET /api/one-pagers/{one_pager_id}
```

### Knowledge Capture

```http
POST /api/knowledge
```

Request:

```json
{
  "question": "Who was the delivery lead?",
  "answer": "Placeholder Delivery Lead",
  "related_document_ids": ["doc_001", "doc_003"],
  "contributor": "Hackathon User"
}
```

Persist the entry in `knowledge.json`.

## Frontend Requirements

### Routes

```text
/                  Main workspace
/one-pagers/:id    One-pager preview
```

### Header

Include:

- PIH logo
- Project Intelligence Hub
- Subtitle: AI-Powered Project Knowledge Assistant
- My Workspaces
- History
- Help
- Placeholder avatar with initials SK

### Left Navigation

Show icons for:

- Home
- Workspaces
- Documents
- One Pagers
- Insights

Only Home needs to work.

### Filter Sidebar

Show:

- Document Type
- Technology
- Industry
- Year
- Clear All Filters

Filter changes must update the API request.

### Search Area

Title:

```text
What are you looking for?
```

Suggested searches:

- Healthcare Data Warehouse
- Snowflake Migration
- Azure Data Engineering
- Customer 360
- GenAI Projects

Clicking a chip should run a search.

### AI Understanding

Show four cards:

1. Documents Found
2. Related Clusters
3. Key Technologies
4. Overall Confidence

Also show:

- Summary text
- Technology badges
- Industry badge
- Placeholder `View Cluster Overview` button

### Document Table

Use TanStack Table.

Columns:

- Select
- Document Name
- Type
- Tags / Extracted Info
- Match Score
- AI Summary
- Added On
- Actions

Add:

- Sorting
- Pagination
- Search within results
- Loading skeleton
- Empty state
- Error state
- Row selection
- Match score progress bar
- Document preview drawer

### Bulk Actions

Show when rows are selected:

- Chat with Selected
- Generate One Pager
- Executive Summary
- Compare Docs
- More

Only `Generate One Pager` must work. Other actions can show a toast.

### AI Assistant Panel

Show:

- Search summary
- Suggested actions
- Top technologies with progress bars
- Knowledge coverage
- Follow-up buttons

Coverage status colors:

- Green for available
- Amber for partial
- Red for missing

### Readiness Modal

When `Generate One Pager` is clicked:

1. Call readiness endpoint.
2. Show coverage and gaps.
3. Allow Cancel or Generate.
4. On Generate, call one-pager endpoint.
5. Navigate to the one-pager page.

### One-Pager Page

Show all generated sections and sources.

Add buttons:

- Download PDF
- Download Markdown
- Copy
- Regenerate

Only Copy must work.

### Knowledge Capture Modal

Fields:

- Missing information
- Question
- Answer
- Contributor
- Related document IDs

Connect it to `POST /api/knowledge`.

## API Client

Use Axios:

```typescript
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api",
  timeout: 30000,
});
```

Create `.env.example`:

```text
VITE_API_BASE_URL=http://localhost:8000/api
```

## TypeScript Rules

- Do not use `any`.
- Create interfaces for every request and response.
- Use functional components.
- Keep API calls outside UI components.
- Use TanStack Query for server state.
- Use local React state for UI state.

## Testing

### Backend

Create tests for:

- Health endpoint
- Search endpoint
- Search filtering
- Document 404
- Readiness endpoint
- Generate one-pager endpoint
- Knowledge save endpoint

### Frontend

At minimum:

- TypeScript build passes
- Search works
- Filters change the request
- Row selection works
- Readiness modal opens
- One-pager page renders

## Commands

Backend:

```bash
cd backend
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

URLs:

```text
Frontend: http://localhost:5173
Backend:  http://localhost:8000
API Docs: http://localhost:8000/docs
```

## Acceptance Criteria

The implementation is complete when:

1. FastAPI runs on port 8000.
2. React runs on port 5173.
3. React calls the FastAPI search endpoint.
4. Search returns placeholder documents.
5. Filters affect results.
6. Results appear in a selectable table.
7. AI cards show API values.
8. AI Assistant shows summary and coverage.
9. Generate One Pager opens readiness modal.
10. One-pager generation creates a placeholder brief.
11. The app navigates to the preview page.
12. Knowledge capture saves data.
13. Backend tests pass.
14. Frontend production build passes.
15. README files include setup instructions.
16. No external services are required.

## Important Constraints

Do not add:

- Authentication
- Real document parsing
- OCR
- Embeddings
- Vector database
- Real LLM calls
- WebSockets
- Redis
- Celery
- Extra pages
- Production deployment

## Codex Execution Order

1. Create folders.
2. Build FastAPI health endpoint and CORS.
3. Create Pydantic models and placeholder JSON.
4. Build search, document, one-pager, and knowledge APIs.
5. Add backend tests and make them pass.
6. Create React + TypeScript + Vite app.
7. Add Tailwind, React Router, TanStack Query, TanStack Table, Axios, and Lucide React.
8. Build dashboard shell.
9. Connect search API.
10. Add filters, selection, sorting, and pagination.
11. Add assistant panel and coverage.
12. Add readiness modal and one-pager generation.
13. Add one-pager preview page.
14. Add knowledge capture modal.
15. Run `pytest`.
16. Run `npm run build`.
17. Fix all errors.
18. Create README files.

## Final Instruction to Codex

Build the complete project directly in the current repository.

Do not only explain the solution.

Create all code, placeholder data, tests, configuration, and README files.

After implementation:

1. Run backend tests.
2. Run the frontend production build.
3. Fix all errors.
4. Summarize the created files.
5. List the exact commands to run the application locally.
