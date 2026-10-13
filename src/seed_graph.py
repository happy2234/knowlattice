from falkordb import FalkorDB

db = FalkorDB(host="localhost", port=6379)
graph = db.select_graph("knowlattice")

# Reset only our demo graph so this script is repeatable.
graph.query("MATCH (n) DETACH DELETE n")

graph.query("""
CREATE
  (priya:Person {
    id: 'person_priya',
    name: 'Priya Sharma',
    role: 'Platform Engineer'
  }),
  (omar:Person {
    id: 'person_omar',
    name: 'Omar Khan',
    role: 'Engineering Manager'
  }),
  (platform:Team {
    id: 'team_platform',
    name: 'Platform Engineering'
  }),
  (atlas:Project {
    id: 'project_atlas',
    name: 'Atlas Migration',
    status: 'blocked'
  }),
  (decision:Decision {
    id: 'decision_db17',
    title: 'Migrate to PostgreSQL 17',
    status: 'approved'
  }),
  (doc:Document {
    id: 'doc_runbook',
    title: 'Atlas Migration Runbook',
    source: 'demo://documents/atlas-runbook'
  }),
  (atlas)-[:OWNED_BY]->(priya),
  (priya)-[:MEMBER_OF]->(platform),
  (omar)-[:MADE]->(decision),
  (decision)-[:AFFECTS]->(atlas),
  (doc)-[:RECORDS]->(decision),
  (priya)-[:RESPONSIBLE_FOR]->(decision)
""")

print("Knowlattice demo graph seeded successfully.")
print("Graph: knowlattice")
print("Sample entities: people, team, project, decision, document")
