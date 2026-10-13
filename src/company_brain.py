from falkordb import FalkorDB


def investigate_company(project_name: str) -> dict:
    db = FalkorDB(host="localhost", port=6379)
    graph = db.select_graph("knowlattice")

    project = graph.query(
        """
        MATCH (p:Project {name: $name})
        RETURN p.name, p.status
        """,
        params={"name": project_name},
    )

    if not project.result_set:
        return {
            "found": False,
            "project": project_name,
            "message": "No matching project exists in the knowledge graph.",
        }

    name, status = project.result_set[0]

    owners = graph.query(
        """
        MATCH (p:Project {name: $name})-[:OWNED_BY]->(owner:Person)
        RETURN owner.name, owner.role
        """,
        params={"name": project_name},
    ).result_set

    tickets = graph.query(
        """
        MATCH (t:Ticket)-[:BLOCKS]->(p:Project {name: $name})
        RETURN t.id, t.title, t.status, t.source
        """,
        params={"name": project_name},
    ).result_set

    messages = graph.query(
        """
        MATCH (m:Message)-[:DISCUSSES]->(p:Project {name: $name})
        RETURN m.id, m.content, m.channel, m.source
        """,
        params={"name": project_name},
    ).result_set

    uploaded_documents = graph.query(
        """
        MATCH (d:IngestedDocument)-[:ABOUT]->(p:Project {name: $name})
        OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:DocumentChunk)
        RETURN d.filename, count(c)
        """,
        params={"name": project_name},
    ).result_set

    decisions = graph.query(
        """
        MATCH (d:Decision)-[:AFFECTS]->(p:Project {name: $name})
        OPTIONAL MATCH (maker:Person)-[:MADE]->(d)
        OPTIONAL MATCH (owner:Person)-[:RESPONSIBLE_FOR]->(d)
        OPTIONAL MATCH (doc:Document)-[:RECORDS]->(d)
        RETURN
            d.title,
            d.status,
            collect(DISTINCT maker.name),
            collect(DISTINCT owner.name),
            collect(DISTINCT doc.title),
            collect(DISTINCT doc.source)
        """,
        params={"name": project_name},
    ).result_set

    return {
        "found": True,
        "project": name,
        "status": status,
        "uploaded_documents": [
            {
                "filename": row[0],
                "pages": row[1],
            }
            for row in uploaded_documents
        ],
        "owners": [
            {"name": row[0], "role": row[1]}
            for row in owners
        ],
        "tickets": [
            {
                "id": row[0],
                "title": row[1],
                "status": row[2],
                "source": row[3],
                "relationship": "BLOCKS",
            }
            for row in tickets
        ],
        "messages": [
            {
                "id": row[0],
                "content": row[1],
                "channel": row[2],
                "source": row[3],
                "relationship": "DISCUSSES",
            }
            for row in messages
        ],
        "decisions": [
            {
                "title": row[0],
                "status": row[1],
                "decision_makers": [v for v in row[2] if v],
                "responsible_people": [v for v in row[3] if v],
                "documents": [
                    {"title": title, "source": source}
                    for title, source in zip(row[4], row[5])
                    if title and source
                ],
            }
            for row in decisions
        ],
    }


if __name__ == "__main__":
    import json
    import sys

    project_name = " ".join(sys.argv[1:]).strip() or "Atlas Migration"
    print(json.dumps(investigate_company(project_name), indent=2))
