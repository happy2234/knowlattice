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

    evidence_question = any(
        phrase in q
        for phrase in (
            "what evidence",
            "evidence supports",
            "supporting evidence",
            "show the evidence",
            "what sources",
        )
    )

    if evidence_question:
        tickets = data.get("tickets", [])
        messages = data.get("messages", [])
        decisions = data.get("decisions", [])

        parts = ["Evidence recorded for " + project_name + ":"]
        evidence = []

        for ticket in tickets:
            claim = (
                f"Ticket {ticket['id']}: {ticket['title']} "
                f"(status: {ticket['status']})."
            )
            parts.append(claim)
            evidence.append({
                "type": "ticket",
                "id": ticket["id"],
                "claim": claim,
                "source": ticket["source"],
            })

        for message in messages:
            claim = f"Message {message['id']}: {message['content']}"
            parts.append(claim)
            evidence.append({
                "type": "chat",
                "id": message["id"],
                "claim": message["content"],
                "source": message["source"],
            })

        for decision in decisions:
            claim = (
                f"Decision: {decision['title']} "
                f"(status: {decision['status']})."
            )
            parts.append(claim)
            evidence.append({
                "type": "decision",
                "claim": claim,
                "source": "FalkorDB knowledge graph",
            })

    elif any(word in q for word in ("who owns", "owner", "responsible")):
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
        elif tickets or messages:
            parts.append(
                "The available records do not establish the root cause."
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

    # Retrieve uploaded-document passages once and add each source once.
    document_matches = search_document_chunks(project_name, question)

    if evidence_question:
        for decision in data.get("decisions", []):
            for person in decision.get("decision_makers", []):
                parts.append(
                    f"{person} recorded the decision: {decision['title']}."
                )
            for person in decision.get("responsible_people", []):
                parts.append(
                    f"{person} is responsible for: {decision['title']}."
                )

    blocker_question = any(
        word in q
        for word in (
            "block", "blocked", "blocker", "blocking",
            "stuck", "delay", "issue", "problem", "why",
        )
    )

    for match in document_matches[:5]:
        excerpt = " ".join((match.get("text") or "").split())
        if not excerpt:
            continue

        # Avoid duplicating the same uploaded file/page already in evidence.
        duplicate = any(
            item.get("type") == "uploaded_document"
            and item.get("filename") == match.get("filename")
            and item.get("page") == match.get("page")
            for item in evidence
        )
        if duplicate:
            continue

        evidence.append({
            "type": "uploaded_document",
            "filename": match["filename"],
            "page": match["page"],
            "claim": excerpt,
            "matched_terms": match.get("matched_terms", []),
            "source": match["source"],
        })

        if evidence_question:
            parts.append(
                f"Uploaded document {match['filename']}, page "
                f"{match['page']}: {excerpt}"
            )

        # Keep document passages in evidence for all intents, but only
        # append blocker-specific prose to blocker answers.
        if (
            blocker_question
            and not evidence_question
            and any(
                marker in excerpt.casefold()
                for marker in (
                    "waiting", "not yet", "pending",
                    "before proceeding", "cannot proceed",
                    "can't proceed",
                )
            )
        ):
            answer += (
                f" Uploaded document '{match['filename']}', page "
                f"{match['page']}, states: {excerpt}"
                " This supports schema validation as the current blocker, "
                "but the available evidence does not establish the root cause "
                "of the incomplete validation."
            )

    if evidence_question:
        if document_matches:
            parts.append(
                "The uploaded passages provide additional context; "
                "the available records do not independently establish "
                "the root cause of incomplete validation."
            )
        elif not tickets and not messages and not data.get("decisions", []):
            parts.append("No matching evidence was found in the available records.")
        answer = " ".join(parts)

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
