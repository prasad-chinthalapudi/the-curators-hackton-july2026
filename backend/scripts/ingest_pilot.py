import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.chroma_indexer import ingest_pilot


if __name__ == "__main__":
    result = ingest_pilot()
    print(
        f"Indexed {result['document_count']} documents / {result['chunk_count']} chunks "
        f"into {result['collection']} ({result['dataset']})."
    )
