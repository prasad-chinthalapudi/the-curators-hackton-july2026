import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.extraction.extractors import EXTRACTORS
from app.extraction.models import (
    ExtractedRecord,
    ExtractionError,
    ExtractionIndex,
    ExtractionMetadata,
    ExtractionOptions,
)


class DocumentExtractionPipeline:
    def __init__(self, options: ExtractionOptions):
        self.options = options

    def discover_files(self) -> list[Path]:
        source = self.options.source_directory.resolve()
        if not source.exists() or not source.is_dir():
            raise ValueError(f"Source directory does not exist: {source}")
        files = [
            path
            for path in source.rglob("*")
            if path.is_file()
            and path.suffix.lower() in EXTRACTORS
            and not path.name.startswith("~$")
        ]
        files.sort(key=lambda path: str(path.relative_to(source)).casefold())
        if self.options.max_files is not None:
            files = files[:self.options.max_files]
        return files

    @staticmethod
    def _document_key(relative_path: Path) -> str:
        normalized = relative_path.as_posix().casefold().encode("utf-8")
        return hashlib.sha256(normalized).hexdigest()[:20]

    def extract(self) -> ExtractionIndex:
        source = self.options.source_directory.resolve()
        files = self.discover_files()
        documents: list[ExtractedRecord] = []
        errors: list[ExtractionError] = []
        for doc_id, path in enumerate(files, 1):
            relative_path = path.relative_to(source)
            suffix = path.suffix.lower()
            try:
                text = EXTRACTORS[suffix](path).strip()
                if not text:
                    raise ValueError("No extractable text was found")
                documents.append(ExtractedRecord(
                    doc_id=doc_id,
                    document_key=self._document_key(relative_path),
                    filename=path.name,
                    relative_path=relative_path.as_posix(),
                    file_type=suffix,
                    raw_text=text,
                    text_length=len(text),
                ))
            except Exception as error:
                errors.append(ExtractionError(
                    relative_path=relative_path.as_posix(),
                    file_type=suffix,
                    error_type=type(error).__name__,
                    message=str(error),
                ))
        return ExtractionIndex(
            metadata=ExtractionMetadata(
                source_directory=str(source),
                total_discovered=len(files),
                total_documents=len(documents),
                total_errors=len(errors),
                supported_file_types=sorted(EXTRACTORS),
            ),
            documents=documents,
            errors=errors,
        )

    def write_index(self, index: ExtractionIndex) -> Path:
        output = self.options.output_file.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = index.model_dump(mode="json")
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".tmp",
            prefix=f"{output.stem}-",
            dir=output.parent,
            delete=False,
        ) as temporary:
            json.dump(payload, temporary, indent=2, ensure_ascii=False)
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, output)
        return output

    def run(self) -> tuple[ExtractionIndex, Path]:
        index = self.extract()
        return index, self.write_index(index)
