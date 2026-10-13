from src import agent


def test_blocker_answer_includes_uploaded_document_evidence(monkeypatch):
    monkeypatch.setattr(
        agent,
        "known_projects",
        lambda: ["Atlas Migration"],
    )
    monkeypatch.setattr(
        agent,
        "answer_company_question",
        lambda name: {
            "found": True,
            "answer": (
                "Atlas Migration is blocked. "
                "The available records do not establish the root cause."
            ),
            "evidence": [],
        },
    )
    monkeypatch.setattr(
        agent,
        "investigate_company",
        lambda name: {
            "found": True,
            "status": "blocked",
            "tickets": [],
            "messages": [],
            "owners": [],
            "decisions": [],
        },
    )
    monkeypatch.setattr(
        agent,
        "search_document_chunks",
        lambda name, question: [
            {
                "filename": "atlas_update.txt",
                "page": 1,
                "text": (
                    "The team is waiting for schema validation. "
                    "Schema validation has not yet been completed."
                ),
                "matched_terms": ["Migration"],
                "source": "upload://doc_test/atlas_update.txt#page=1",
            }
        ],
    )

    result = agent.answer_question("What is blocking Atlas Migration?")

    assert result["found"] is True
    assert "waiting for schema validation" in result["answer"]
    assert "root cause" in result["answer"]
    assert any(
        item["type"] == "uploaded_document"
        and item["filename"] == "atlas_update.txt"
        and item["page"] == 1
        for item in result["evidence"]
    )
