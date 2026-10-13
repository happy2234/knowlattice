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


def test_evidence_question_returns_direct_evidence_summary(monkeypatch):
    monkeypatch.setattr(
        agent, "known_projects", lambda: ["Atlas Migration"]
    )
    monkeypatch.setattr(
        agent,
        "answer_company_question",
        lambda name: {
            "found": True,
            "answer": "Generic project summary.",
            "evidence": [
                {
                    "type": "ticket",
                    "id": "ticket_104",
                    "claim": "Ticket reports: PostgreSQL migration blocked",
                    "source": "FalkorDB knowledge graph",
                },
                {
                    "type": "chat",
                    "id": "message_208",
                    "claim": "The migration is waiting on schema validation.",
                    "source": "FalkorDB knowledge graph",
                },
            ],
        },
    )
    monkeypatch.setattr(
        agent,
        "investigate_company",
        lambda name: {
            "found": True,
            "status": "blocked",
            "tickets": [
                {
                    "id": "ticket_104",
                    "title": "PostgreSQL migration blocked",
                    "status": "open",
                    "source": "FalkorDB knowledge graph",
                }
            ],
            "messages": [
                {
                    "id": "message_208",
                    "content": "The migration is waiting on schema validation.",
                    "source": "FalkorDB knowledge graph",
                }
            ],
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
                "text": "Schema validation has not yet been completed.",
                "matched_terms": ["validation"],
                "source": "upload://doc_test/atlas_update.txt#page=1",
            }
        ],
    )

    result = agent.answer_question(
        "What evidence supports this answer for Atlas Migration?"
    )

    assert result["found"] is True
    assert "ticket_104" in result["answer"]
    assert "message_208" in result["answer"]
    assert "atlas_update.txt" in result["answer"]
    assert "root cause" in result["answer"].lower()
