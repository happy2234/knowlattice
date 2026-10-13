from falkordb import FalkorDB


def discover_relationships(project_name: str) -> dict:
    """Discover people, decisions, and documents connected to a project."""
    db = FalkorDB(host="localhost", port=6379)
    graph = db.select_graph("knowlattice")

    project_result = graph.query(
        """
        MATCH (p:Project {name: $name})
        RETURN p.name AS name, p.status AS status
        """,
        params={"name": project_name},
    )

    if not project_result.result_set:
        return {
            "found": False,
            "project": project_name,
            "message": "No matching project exists in the knowledge graph.",
        }

    _, status = project_result.result_set[0]

    owner_result = graph.query(
        """
        MATCH (p:Project {name: $name})-[:OWNED_BY]->(person:Person)
        RETURN DISTINCT person.name AS name
        """,
        params={"name": project_name},
    )

    decision_result = graph.query(
        """
        MATCH (d:Decision)-[:AFFECTS]->(p:Project {name: $name})
        OPTIONAL MATCH (maker:Person)-[:MADE]->(d)
        OPTIONAL MATCH (responsible:Person)-[:RESPONSIBLE_FOR]->(d)
        OPTIONAL MATCH (doc:Document)-[:RECORDS]->(d)
        RETURN
            d.title AS title,
            d.status AS status,
            maker.name AS decision_maker,
            responsible.name AS responsible_person,
            doc.title AS source_document
        """,
        params={"name": project_name},
    )

    owners = sorted({
        row[0]
        for row in owner_result.result_set
        if row[0] is not None
    })

    # Deduplicate results if a decision has multiple related people
    # or source documents.
    decisions = {}

    for row in decision_result.result_set:
        title, decision_status, maker, responsible, document = row

        if title is None:
            continue

        item = decisions.setdefault(
            title,
            {
                "title": title,
                "status": decision_status,
                "decision_makers": [],
                "responsible_people": [],
                "source_documents": [],
            },
        )

        if maker and maker not in item["decision_makers"]:
            item["decision_makers"].append(maker)

        if responsible and responsible not in item["responsible_people"]:
            item["responsible_people"].append(responsible)

        if document and document not in item["source_documents"]:
            item["source_documents"].append(document)

    return {
        "found": True,
        "project": project_name,
        "status": status,
        "owners": owners,
        "decisions": list(decisions.values()),
    }
