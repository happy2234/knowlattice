import pytest

from src.ingest_documents import extract_pages


def test_extract_txt_preserves_text_and_page_number():
    content = b"Atlas Migration is waiting on schema validation."

    pages = extract_pages("notes.txt", content)

    assert len(pages) == 1
    assert pages[0]["page"] == 1
    assert "schema validation" in pages[0]["text"]


def test_rejects_unsupported_file_type():
    with pytest.raises(ValueError, match="Only PDF and TXT"):
        extract_pages("notes.docx", b"some content")


def test_rejects_empty_file():
    with pytest.raises(ValueError, match="empty"):
        extract_pages("notes.txt", b"")


def test_rejects_invalid_txt_encoding():
    with pytest.raises(ValueError, match="UTF-8"):
        extract_pages("notes.txt", b"\xff\xfe\xfa")


def test_rejects_oversized_file():
    from src.ingest_documents import MAX_FILE_BYTES

    with pytest.raises(ValueError, match="20 MB"):
        extract_pages("notes.txt", b"x" * (MAX_FILE_BYTES + 1))


def test_search_ranking_prefers_blocker_sentences(monkeypatch):
    from types import SimpleNamespace
    from src import ingest_documents

    class FakeGraph:
        def query(self, query, params=None):
            return SimpleNamespace(result_set=[
                (
                    "project_notes.txt",
                    1,
                    (
                        "Atlas Migration Project Update. "
                        "Priya Sharma owns the project. "
                        "The team is waiting for schema validation "
                        "before proceeding with PostgreSQL 17. "
                        "Schema validation has not yet been completed."
                    ),
                    "upload://doc_test/project_notes.txt#page=1",
                )
            ])

    class FakeDB:
        def __init__(self, **kwargs):
            pass

        def select_graph(self, name):
            return FakeGraph()

    monkeypatch.setattr(ingest_documents, "FalkorDB", FakeDB)

    results = ingest_documents.search_document_chunks(
        "Atlas Migration",
        "What is blocking Atlas Migration?",
    )

    assert len(results) == 1
    assert "waiting for schema validation" in results[0]["text"]
    assert "Schema validation has not yet been completed" in results[0]["text"]
    assert "CURRENT BLOCKER" not in results[0]["text"]
    assert "Priya Sharma owns the project" not in results[0]["text"]
    assert results[0]["source"].endswith("#page=1")

    # A substring of the product name "Knowlattice" must not count as
    # a match for the standalone search term "lattice".
    assert ingest_documents.search_document_chunks(
        "Atlas Migration", "lattice"
    ) == []
