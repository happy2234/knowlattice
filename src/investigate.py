from falkordb import FalkorDB


def investigate_project(project_name: str) -> dict:
    """Retrieve a project's connected company knowledge from FalkorDB."""
    db = FalkorDB(host="localhost", port=6379)
    graph = db.select_graph("knowlattice")

    query = """
    MATCH (p:Project {name: $project_name})
    OPTIONAL MATCH (p)-[:OWNED_BY]->(owner:Person)
    OPTIONAL MATCH (decision:Decision)-[:AFFECTS]->(p)
    OPTIONAL MATCH (maker:Person)-[:MADE]->(decision)
    OPTIONAL MATCH (doc:Document)-[:RECORDS]->(decision)
    RETURN
        p.name AS project,
        p.status AS status,
        collect(DISTINCT owner.name) AS owners,
        collect(DISTINCT decision.title) AS decisions,
        collect(DISTINCT maker.name) AS decision_makers,
        collect(DISTINCT doc.title) AS documents
    """

    result = graph.query(
        query,
        params={"project_name": project_name},
    )

    if not result.result_set:
        return {
            "found": False,
            "project": project_name,
            "message": "No matching project exists in the knowledge graph.",
        }

    row = result.result_set[0]

    def clean(values):
        return [value for value in values if value is not None]

    return {
        "found": True,
        "project": row[0],
        "status": row[1],
        "owners": clean(row[2]),
        "decisions": clean(row[3]),
        "decision_makers": clean(row[4]),
        "documents": clean(row[5]),
    }


if __name__ == "__main__":
    import json
    import sys

    name = " ".join(sys.argv[1:]).strip() or "Atlas Migration"
    print(json.dumps(investigate_project(name), indent=2))
