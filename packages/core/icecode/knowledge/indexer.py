"""DocumentIndexer — chunks and embeds local files for RAG."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger

# Supported file extensions
SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".py", ".ts", ".js", ".tsx", ".jsx",
    ".java", ".go", ".rs", ".cpp", ".c", ".h", ".cs", ".rb", ".php",
    ".html", ".htm", ".css", ".scss", ".json", ".yaml", ".yml", ".toml",
    ".xml", ".csv", ".sh", ".bash", ".env", ".conf", ".ini", ".cfg",
    ".rst", ".tex", ".sql", ".graphql", ".proto",
}

CHUNK_SIZE = 512       # characters per chunk
CHUNK_OVERLAP = 80     # overlap between consecutive chunks


def _chunk_text(text: str, source: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[Dict[str, Any]]:
    """Split text into overlapping chunks."""
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    chunk_idx = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        # Try to break at sentence/line boundary
        if end < len(text):
            for sep in ["\n\n", "\n", ". ", " "]:
                pos = text.rfind(sep, start, end)
                if pos > start + chunk_size // 2:
                    end = pos + len(sep)
                    break

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunk_id = hashlib.md5(f"{source}:{chunk_idx}:{chunk_text[:50]}".encode()).hexdigest()[:16]
            chunks.append({
                "id": chunk_id,
                "text": chunk_text,
                "source": source,
                "chunk_idx": chunk_idx,
                "char_start": start,
                "char_end": end,
            })
            chunk_idx += 1

        start = end - overlap if end < len(text) else len(text)

    return chunks


def _read_file(path: Path) -> Optional[str]:
    """Read file content, handling encoding issues."""
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        try:
            import PyPDF2
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                pages = []
                for page in reader.pages[:50]:  # max 50 pages
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                return "\n\n".join(pages)
        except ImportError:
            logger.warning("PyPDF2 not installed, skipping PDF")
            return None
        except Exception as e:
            logger.warning(f"PDF read error {path}: {e}")
            return None

    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"Cannot read {path}: {e}")
        return None


class DocumentIndexer:
    """Chunks documents from files or directories."""

    def index_file(self, path: str | Path) -> List[Dict[str, Any]]:
        """Return chunks from a single file."""
        p = Path(path).expanduser().resolve()
        if not p.exists() or not p.is_file():
            logger.warning(f"File not found: {path}")
            return []

        if p.suffix.lower() not in SUPPORTED_EXTENSIONS and p.suffix.lower() != ".pdf":
            logger.debug(f"Skipping unsupported extension: {p.suffix}")
            return []

        content = _read_file(p)
        if not content:
            return []

        chunks = _chunk_text(content, str(p))
        logger.info(f"Indexed {p.name}: {len(chunks)} chunks")
        return chunks

    def index_directory(
        self,
        path: str | Path,
        recursive: bool = True,
        exclude_patterns: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        """Return all chunks from files in a directory."""
        p = Path(path).expanduser().resolve()
        if not p.exists() or not p.is_dir():
            logger.warning(f"Directory not found: {path}")
            return []

        exclude = set(exclude_patterns or [
            "node_modules", ".git", ".venv", "__pycache__", "dist", "build",
            ".pytest_cache", ".mypy_cache", "*.pyc",
        ])

        all_chunks = []
        pattern = "**/*" if recursive else "*"

        for file_path in p.glob(pattern):
            if not file_path.is_file():
                continue
            # Skip excluded paths
            if any(ex in file_path.parts or file_path.match(ex) for ex in exclude):
                continue
            if file_path.suffix.lower() in SUPPORTED_EXTENSIONS or file_path.suffix.lower() == ".pdf":
                all_chunks.extend(self.index_file(file_path))

        logger.info(f"Indexed directory {p.name}: {len(all_chunks)} total chunks")
        return all_chunks
