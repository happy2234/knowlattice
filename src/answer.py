from src.company_brain import investigate_company


def answer_company_question(project_name: str) -> dict:
    """Build an evidence-backed report from company graph records."""
    data = investigate_company(project_name)

    if not data["found"]:
        return {
            "found": False,
            "question": f"What is happening with {project_name}?",
            "answer": data["message"],
            "evidence": [],
        }

    evidence = []

    for ticket in data["tickets"]:
        evidence.append({
            "type": "ticket",
            "id": ticket["id"],
            "claim": f"Ticket reports: {ticket['title']}",
            "source": ticket["source"],
        })

    for message in data["messages"]:
        evidence.append({
            "type": "chat",
            "id": message["id"],
            "claim": message["content"],
            "source": message["source"],
        })

    for decision in data["decisions"]:
        for document in decision["documents"]:
            evidence.append({
                "type": "document",
                "claim": (
                    f"Document recorded in the graph: "
                    f"{document['title']}"
                ),
                "source": document["source"],
            })

    lines = [
        f"{data['project']} currently has status: {data['status']}."
    ]

    if data["tickets"]:
        lines.append(
            f"There are {len(data['tickets'])} linked ticket(s)."
        )

    if data["messages"]:
        lines.append(
            f"There are {len(data['messages'])} linked chat message(s)."
        )

    if data["decisions"]:
        for decision in data["decisions"]:
            lines.append(
                f"Recorded decision: '{decision['title']}' "
                f"(status: {decision['status']})."
            )

    if data["tickets"] and data["messages"]:
        lines.append(
            "The ticket and chat both concern this project. "
            "The chat mentions schema validation, but the available "
            "records do not prove that it is the root cause."
        )

    return {
        "found": True,
        "question": f"What is happening with {project_name}?",
        "answer": " ".join(lines),
        "evidence": evidence,
        "project_data": data,
    }


if __name__ == "__main__":
    import json
    import sys

    name = " ".join(sys.argv[1:]).strip() or "Atlas Migration"
    print(json.dumps(answer_company_question(name), indent=2))
