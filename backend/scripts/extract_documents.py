import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.extraction.models import ExtractionOptions
from app.extraction.pipeline import DocumentExtractionPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract PIH documents into the JSON index contract."
    )
    parser.add_argument("source", type=Path, help="Directory containing project files")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output JSON file; existing files are atomically replaced",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Optional deterministic development limit",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    options = ExtractionOptions(
        source_directory=arguments.source,
        output_file=arguments.output,
        max_files=arguments.max_files,
    )
    try:
        index, output = DocumentExtractionPipeline(options).run()
    except Exception as error:
        print(f"Extraction failed: {error}", file=sys.stderr)
        return 1
    print(
        f"Extracted {index.metadata.total_documents}/"
        f"{index.metadata.total_discovered} documents; "
        f"errors={index.metadata.total_errors}; output={output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
