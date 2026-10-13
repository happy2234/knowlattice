from falkordb import FalkorDB

db = FalkorDB(host="localhost", port=6379)
graph = db.select_graph("knowlattice")

# Add a ticket linked to the existing Atlas Migration project.
graph.query("""
MERGE (t:Ticket {id: 'ticket_104'})
ON CREATE SET
    t.title = 'PostgreSQL migration blocked',
    t.status = 'open',
    t.source = 'demo://tickets/104'
WITH t
MATCH (p:Project {name: 'Atlas Migration'})
MERGE (t)-[:BLOCKS]->(p)
""")

# Add a chat message that references the same project.
graph.query("""
MERGE (m:Message {id: 'message_208'})
ON CREATE SET
    m.content = 'The migration is waiting on schema validation.',
    m.source = 'demo://chat/208',
    m.channel = 'engineering'
WITH m
MATCH (p:Project {name: 'Atlas Migration'})
MERGE (m)-[:DISCUSSES]->(p)
""")

# Link the ticket to the decision it concerns.
graph.query("""
MATCH (t:Ticket {id: 'ticket_104'})
MATCH (d:Decision {title: 'Migrate to PostgreSQL 17'})
MERGE (t)-[:RELATES_TO]->(d)
""")

print("Company records added: ticket, chat message, and relationships.")
