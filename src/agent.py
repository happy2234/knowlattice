from falkordb import FalkorDB
from src.company_brain import investigate_company
from src.answer import answer_company_question
from src.ingest_documents import search_document_chunks


def known_projects() -> list[str]:
    db = FalkorDB(host="localhost", port=6379)
    graph = db.select_graph("knowlattice")

    result = graph.query(
        "MATCH (p:Project) RETURN p.name AS name"
    )
    return sorted(
        row[0] for row in result.result_set if row[0]
    )


def answer_question(question: str) -> dict:
    """Route a question to safe, graph-backed investigation tools."""
    question = question.strip()

    if not question:
        return {
            "found": False,
            "answer": "Please enter a question.",
            "evidence": [],
        }

    matches = [
        name for name in known_projects()
        if name.casefold() in question.casefold()
    ]

    if not matches:
        return {
            "found": False,
            "question": question,
            "answer": (
                "I couldn't identify a known project in your question. "
                "Please include the project name."
            ),
            "evidence": [],
        }

    # Prefer the longest matching project name if names overlap.
    project_name = max(matches, key=len)
    report = answer_company_question(project_name)

    if not report["found"]:
        return report

    data = investigate_company(project_name)
    q = question.casefold()

    evidence = report["evidence"]

    if any(word in q for word in ("who owns", "owner", "responsible")):
        project_owners = data.get("owners", [])

        answer = (
            f"{project_name} is owned by "
            + (
                ", ".join(owner["name"] for owner in project_owners)
                if project_owners
                else "no recorded owner in the graph"
            )
            + "."
        )

        evidence = [
            {
                "type": "graph_relationship",
                "claim": (
                    f"{project_name} -[OWNED_BY]-> {owner['name']}"
                    + (f" ({owner['role']})" if owner.get("role") else "")
                ),
                "source": "FalkorDB knowledge graph",
            }
            for owner in project_owners
        ]

        responsible = sorted({
            person
            for decision in data["decisions"]
            for person in decision["responsible_people"]
        })

        if responsible:
            answer += (
                " Recorded decision responsibility: "
                + ", ".join(responsible)
                + "."
            )
            evidence.extend(
                {
                    "type": "graph_relationship",
                    "claim": f"{person} -[RESPONSIBLE_FOR]-> a recorded decision",
                    "source": "FalkorDB knowledge graph",
                }
                for person in responsible
            )

    elif any(word in q for word in ("decision", "approved", "decided")):
        decisions = data["decisions"]
        if decisions:
            answer = "Recorded decisions: " + "; ".join(
                f"{d['title']} ({d['status']})"
                for d in decisions
            ) + "."

            evidence = []
            for decision in decisions:
                evidence.append({
                    "type": "decision",
                    "claim": (
                        f"{decision['title']} has recorded status "
                        f"{decision['status']}."
                    ),
                    "source": "FalkorDB knowledge graph",
                })
                for person in decision["decision_makers"]:
                    evidence.append({
                        "type": "graph_relationship",
                        "claim": f"{person} -[MADE]-> {decision['title']}",
                        "source": "FalkorDB knowledge graph",
                    })
                for doc in decision["documents"]:
                    evidence.append({
                        "type": "document",
                        "claim": (
                            f"Document records the decision: {doc['title']}"
                        ),
                        "source": doc["source"],
                    })
        else:
            answer = "No decisions are linked to this project in the graph."
            evidence = []

    elif any(word in q for word in ("block", "issue", "stuck", "why")):
        tickets = data["tickets"]
        messages = data["messages"]

        parts = [f"{project_name} has status: {data['status']}."]
        parts.extend(
            f"Ticket {t['id']}: {t['title']} (status: {t['status']})."
            for t in tickets
        )
        parts.extend(
            f"Chat evidence: {m['content']}"
            for m in messages
        )
        if tickets and messages:
            parts.append(
                "These records suggest a possible connection, "
                "but do not independently establish the root cause."
            )
        answer = " ".join(parts)
        evidence = [
            {
                "type": "ticket",
                "id": ticket["id"],
                "claim": f"Ticket reports: {ticket['title']}",
                "source": ticket["source"],
            }
            for ticket in tickets
        ] + [
            {
                "type": "chat",
                "id": message["id"],
                "claim": message["content"],
                "source": message["source"],
            }
            for message in messages
        ]

    else:
        answer = report["answer"]

    # Retrieve keyword-matched passages from uploaded project documents.
    document_matches = search_document_chunks(project_name, question)

    for match in document_matches[:5]:
        excerpt = " ".join((match.get("text") or "").split())
        if len(excerpt) > 700:
            excerpt = excerpt[:700].rsplit(" ", 1)[0] + "..."

        evidence.append({
            "type": "uploaded_document",
            "filename": match["filename"],
            "page": match["page"],
            "claim": excerpt,
            "matched_terms": match.get("matched_terms", []),
            "source": match["source"],
        })

    if document_matches:
        passages = []
        for match in document_matches[:3]:
            excerpt = " ".join((match.get("text") or "").split())
            if len(excerpt) > 500:
                excerpt = excerpt[:500].rsplit(" ", 1)[0] + "..."
            passages.append(
                f"{match['filename']} (page {match['page']}): {excerpt}"
            )

        answer += " Relevant uploaded-document passages: " + " ".join(passages)

    return {
        "found": True,
        "question": question,
        "project": project_name,
        "answer": answer,
        "evidence": evidence,
    }


if __name__ == "__main__":
    import json
    import sys

    question = " ".join(sys.argv[1:])
    print(json.dumps(answer_question(question), indent=2))
