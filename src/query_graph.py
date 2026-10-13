from falkordb import FalkorDB

db = FalkorDB(host="localhost", port=6379)
graph = db.select_graph("knowlattice")

query = """
MATCH
  (p:Project {name: 'Atlas Migration'})
MATCH
  (p)<-[:AFFECTS]-(d:Decision)<-[:MADE]-(person:Person)
MATCH
  (p)-[:OWNED_BY]->(owner:Person)
OPTIONAL MATCH
  (doc:Document)-[:RECORDS]->(d)
RETURN
  p.name AS project,
  p.status AS status,
  owner.name AS owner,
  d.title AS decision,
  person.name AS decision_maker,
  doc.title AS source_document
"""

result = graph.query(query)

for row in result.result_set:
    print(f"Project: {row[0]}")
    print(f"Status: {row[1]}")
    print(f"Owner: {row[2]}")
    print(f"Decision: {row[3]}")
    print(f"Decision maker: {row[4]}")
    print(f"Evidence document: {row[5]}")
    print("-" * 35)
