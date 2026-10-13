from src.answer import answer_company_question


def test_answer_includes_evidence_and_limits_claims():
    result = answer_company_question("Atlas Migration")

    assert result["found"] is True
    assert "blocked" in result["answer"]
    assert "root cause" in result["answer"]
    assert any(
        item["source"] == "demo://tickets/104"
        for item in result["evidence"]
    )
    assert any(
        item["source"] == "demo://chat/208"
        for item in result["evidence"]
    )


def test_unknown_project_has_no_evidence():
    result = answer_company_question("Unknown Project")

    assert result["found"] is False
    assert result["evidence"] == []
