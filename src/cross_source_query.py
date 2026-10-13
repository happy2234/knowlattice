from falkordb import FalkorDB

db = FalkorDB(host="localhost", port=6379)
graph = db.select_graph("knowlattice")

query = """
MATCH (source)-[r]->(p:Project {name: $project})
WHERE source:Ticket OR source:Message
RETURN
    labels(source) AS source_type,
    source.id AS source_id,
    source.title AS title,
    source.content AS message,
    type(r) AS relationship,
    source.source AS source_uri
ORDER BY source_type
"""

result = graph.query(
    query,
    params={"project": "Atlas Migration"},
)

for row in result.result_set:
    print({
        "type": row[0],
        "id": row[1],
        "title": row[2],
        "message": row[3],
        "relationship": row[4],
        "source": row[5],
    })
