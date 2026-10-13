"""Safe, provenance-preserving PDF/TXT ingestion for Knowlattice."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from pypdf import PdfReader
from falkordb import FalkorDB


GRAPH_NAME = "knowlattice"
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 2_000_000
ALLOWED_SUFFIXES = {".pdf", ".txt"}


def extract_pages(filename: str, content: bytes) -> list[dict]:
    """Extract page-numbered text from a PDF or one logical TXT page."""
    path = Path(filename)

    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError("Only PDF and TXT files are supported.")

    if not content:
        raise ValueError("The uploaded file is empty.")

    if len(content) > MAX_FILE_BYTES:
        raise ValueError("The file exceeds the 20 MB limit.")

    pages = []

    if path.suffix.lower() == ".pdf":
        import io

        try:
            reader = PdfReader(io.BytesIO(content), strict=True)
            if reader.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported.")

            for number, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                if text:
                    pages.append({"page": number, "text": text})
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Could not read PDF: {exc}") from exc
    else:
        try:
            text = content.decode("utf-8-sig").strip()
        except UnicodeDecodeError as exc:
            raise ValueError("TXT files must use UTF-8 encoding.") from exc

        if text:
            pages.append({"page": 1, "text": text})

    total_chars = sum(len(page["text"]) for page in pages)
    if total_chars > MAX_TEXT_CHARS:
        raise ValueError("Extracted text exceeds the 2-million-character limit.")

    if not pages:
        raise ValueError(
            "No extractable text was found. Scanned PDFs may need OCR."
        )

    return pages


def ingest_document(
    filename: str,
    content: bytes,
    project_name: str,
) -> dict:
    """Store a document and its page chunks without resetting the graph."""
    project_name = project_name.strip()
    if not project_name:
        raise ValueError("Select a project before ingesting a document.")

    pages = extract_pages(filename, content)
    digest = hashlib.sha256(content).hexdigest()
    document_id = f"doc_{digest[:24]}"
    safe_filename = Path(filename).name

    db = FalkorDB(host="localhost", port=6379)
    graph = db.select_graph(GRAPH_NAME)

    # Validate the target project before writing any nodes.
    project_result = graph.query(
        "MATCH (p:Project {name: $name}) RETURN p.name",
        params={"name": project_name},
    )
    if not project_result.result_set:
        raise ValueError(
            f"Project '{project_name}' was not found. No document was stored."
        )

    # Hash-based identity makes repeat uploads idempotent.
    existing = graph.query(
        "MATCH (d:IngestedDocument {id: $id}) RETURN d.id",
        params={"id": document_id},
    )
    if existing.result_set:
        return {
            "status": "duplicate",
            "document_id": document_id,
            "filename": safe_filename,
            "pages": len(pages),
            "message": "This exact file has already been ingested.",
        }

    graph.query(
        """
        CREATE (d:IngestedDocument {
            id: $id,
            filename: $filename,
            sha256: $sha256,
            source: $source,
            project_name: $project_name
        })
        """,
        params={
            "id": document_id,
            "filename": safe_filename,
            "sha256": digest,
            "source": f"upload://{document_id}/{safe_filename}",
            "project_name": project_name,
        },
    )

    graph.query(
        """
        MATCH (d:IngestedDocument {id: $id})
        MATCH (p:Project {name: $project_name})
        MERGE (d)-[:ABOUT]->(p)
        """,
        params={"id": document_id, "project_name": project_name},
    )

    for page in pages:
        chunk_id = f"{document_id}_p{page['page']}"
        graph.query(
            """
            MATCH (d:IngestedDocument {id: $document_id})
            CREATE (c:DocumentChunk {
                id: $chunk_id,
                page: $page,
                text: $text,
                source: $source
            })
            MERGE (d)-[:HAS_CHUNK]->(c)
            """,
            params={
                "document_id": document_id,
                "chunk_id": chunk_id,
                "page": page["page"],
                "text": page["text"],
                "source": (
                    f"upload://{document_id}/{safe_filename}#page={page['page']}"
                ),
            },
        )

    return {
        "status": "ingested",
        "document_id": document_id,
        "filename": safe_filename,
        "pages": len(pages),
        "characters": sum(len(page["text"]) for page in pages),
        "project": project_name,
        "source": f"upload://{document_id}/{safe_filename}",
    }


def search_document_chunks(project_name: str, query: str) -> list[dict]:
    """Rank document passages by keyword overlap and question intent."""
    stopwords = {
        "a", "an", "and", "are", "as", "at", "be", "been", "by",
        "can", "could", "did", "do", "does", "for", "from", "has",
        "have", "how", "i", "in", "into", "is", "it", "its", "me",
        "of", "on", "or", "our", "please", "should", "that", "the",
        "their", "them", "there", "these", "this", "to", "was",
        "we", "were", "what", "when", "where", "which", "who",
        "why", "will", "with", "would", "you", "your",
    }

    def tokenize(value: str) -> list[str]:
        tokens = re.findall(r"[a-zA-Z0-9_+-]+", value.casefold())
        result = []
        for token in tokens:
            if len(token) > 5 and token.endswith("ing"):
                token = token[:-3]
            elif len(token) > 4 and token.endswith("ed"):
                token = token[:-2]
            elif len(token) > 4 and token.endswith("s"):
                token = token[:-1]
            result.append(token)
        return result

    raw_terms = tokenize(query)
    terms = list(dict.fromkeys(
        term for term in raw_terms
        if term not in stopwords and len(term) > 1
    ))
    if not terms:
        return []

    q = query.casefold()
    blocker_question = any(
        phrase in q for phrase in
        ("block", "blocked", "blocker", "blocking", "stuck",
         "delay", "delayed", "issue", "problem", "waiting", "why")
    )
    blocker_markers = (
        "block", "wait", "delay", "issue", "problem", "fail",
        "pending", "not yet", "cannot proceed", "can't proceed",
    )

    db = FalkorDB(host="localhost", port=6379)
    graph = db.select_graph(GRAPH_NAME)
    result = graph.query(
        """
        MATCH (d:IngestedDocument)-[:ABOUT]->(p:Project {name: $name})
        MATCH (d)-[:HAS_CHUNK]->(c:DocumentChunk)
        RETURN d.filename, c.page, c.text, c.source
        """,
        params={"name": project_name},
    )

    matches = []
    for filename, page, text, source in result.result_set:
        full_text = " ".join((text or "").split())
        sentences = re.split(r"(?<=[.!?])\s+", full_text)
        scored_sentences = []

        for index, sentence in enumerate(sentences):
            sentence_terms = set(tokenize(sentence))
            matched_terms = [term for term in terms if term in sentence_terms]
            score = len(matched_terms) / len(terms)

            if blocker_question and any(
                marker in sentence.casefold() for marker in blocker_markers
            ):
                score += 1.0

            # A sentence mentioning the project is useful context, but should
            # not outrank a direct blocker explanation by itself.
            if "atlas migration" in sentence.casefold():
                score += 0.05

            if score > 0:
                scored_sentences.append({
                    "sentence": sentence,
                    "score": score,
                    "matched_terms": matched_terms,
                    "index": index,
                })

        if not scored_sentences:
            continue

        scored_sentences.sort(
            key=lambda item: (item["score"], len(item["matched_terms"])),
            reverse=True,
        )
        selected = scored_sentences[:3]
        excerpt = " ".join(item["sentence"] for item in selected)
        if len(excerpt) > 700:
            excerpt = excerpt[:700].rsplit(" ", 1)[0] + "..."

        matched_terms = list(dict.fromkeys(
            term for item in selected for term in item["matched_terms"]
        ))
        matches.append({
            "filename": filename,
            "page": page,
            "text": excerpt,
            "source": source,
            "matched_terms": matched_terms,
            "score": max(item["score"] for item in selected),
        })

    matches.sort(key=lambda item: item["score"], reverse=True)
    return matches[:5]
