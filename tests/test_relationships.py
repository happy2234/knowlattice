from src.relationships import discover_relationships


def test_relationships_distinguish_company_roles():
    result = discover_relationships("Atlas Migration")

    assert result["found"] is True
    assert result["status"] == "blocked"
    assert "Priya Sharma" in result["owners"]

    assert len(result["decisions"]) == 1
    decision = result["decisions"][0]

    assert decision["title"] == "Migrate to PostgreSQL 17"
    assert decision["status"] == "approved"
    assert "Omar Khan" in decision["decision_makers"]
    assert "Priya Sharma" in decision["responsible_people"]
    assert "Atlas Migration Runbook" in decision["source_documents"]


def test_relationships_handle_unknown_project():
    result = discover_relationships("Unknown Project")

    assert result["found"] is False
    assert result["project"] == "Unknown Project"
