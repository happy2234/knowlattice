from src.investigate import investigate_project


def test_known_project_returns_connected_facts():
    result = investigate_project("Atlas Migration")

    assert result["found"] is True
    assert result["project"] == "Atlas Migration"
    assert result["status"] == "blocked"
    assert "Priya Sharma" in result["owners"]
    assert "Migrate to PostgreSQL 17" in result["decisions"]
    assert "Omar Khan" in result["decision_makers"]
    assert "Atlas Migration Runbook" in result["documents"]


def test_unknown_project_returns_not_found():
    result = investigate_project("Unknown Project")

    assert result["found"] is False
    assert result["project"] == "Unknown Project"


def test_missing_project_does_not_return_company_facts():
    result = investigate_project("Nonexistent Project XYZ")

    assert result["found"] is False
    assert "owners" not in result
    assert "decisions" not in result
