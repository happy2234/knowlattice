import json

import streamlit as st

from src.agent import answer_question, known_projects
from src.company_brain import investigate_company


st.set_page_config(
    page_title="Knowlattice",
    page_icon="K",
    layout="wide",
)

st.title("Knowlattice")
st.caption("The intelligence behind how your company works.")
st.write(
    "Investigate projects, trace decisions, find owners, "
    "and inspect the evidence connected in your company graph."
)


def make_graph(data):
    """Build a Graphviz view from the retrieved project relationships."""
    nodes = []
    edges = []

    def add_node(node_id, label, shape="box"):
        nodes.append(
            f"{node_id} [label={json.dumps(str(label))}, shape={shape}];"
        )

    def add_edge(source, target, relationship):
        edges.append(
            f"{source} -> {target} "
            f"[label={json.dumps(relationship)}];"
        )

    add_node("project", data["project"], "doublecircle")

    for i, owner in enumerate(data.get("owners", [])):
        node_id = f"owner_{i}"
        add_node(node_id, f"{owner['name']}\n{owner.get('role') or 'Person'}")
        add_edge("project", node_id, "OWNED_BY")

    for i, ticket in enumerate(data.get("tickets", [])):
        node_id = f"ticket_{i}"
        add_node(node_id, f"{ticket['title']}\n{ticket['status']}")
        add_edge(node_id, "project", "BLOCKS")

    for i, message in enumerate(data.get("messages", [])):
        node_id = f"message_{i}"
        add_node(node_id, message["content"])
        add_edge(node_id, "project", "DISCUSSES")

    for i, decision in enumerate(data.get("decisions", [])):
        decision_id = f"decision_{i}"
        add_node(
            decision_id,
            f"{decision['title']}\n{decision['status']}",
            "diamond",
        )
        add_edge(decision_id, "project", "AFFECTS")

        for j, person in enumerate(decision.get("decision_makers", [])):
            person_id = f"maker_{i}_{j}"
            add_node(person_id, person, "ellipse")
            add_edge(person_id, decision_id, "MADE")

        for j, person in enumerate(decision.get("responsible_people", [])):
            person_id = f"responsible_{i}_{j}"
            add_node(person_id, person, "ellipse")
            add_edge(person_id, decision_id, "RESPONSIBLE_FOR")

        for j, document in enumerate(decision.get("documents", [])):
            document_id = f"document_{i}_{j}"
            add_node(document_id, document["title"])
            add_edge(document_id, decision_id, "RECORDS")

    return (
        "digraph Knowlattice {\n"
        "  rankdir=LR;\n"
        '  graph [pad="0.3", nodesep="0.5", ranksep="0.8"];\n'
        '  node [style="rounded,filled", fillcolor="#EAF2FF", '
        'color="#6485B8", fontname="sans-serif"];\n'
        '  edge [fontname="sans-serif", color="#6B7280"];\n'
        + "\n".join(nodes)
        + "\n"
        + "\n".join(edges)
        + "\n}"
    )


try:
    projects = known_projects()
except Exception as exc:
    st.error(
        "Cannot connect to FalkorDB. Check that your database container "
        "is running, then reload this page."
    )
    st.exception(exc)
    st.stop()

if not projects:
    st.warning("No projects were found in the knowledge graph.")
    st.stop()

with st.sidebar:
    st.header("Company knowledge")
    selected_project = st.selectbox("Project", projects)
    st.divider()
    st.caption("Available investigation types")
    st.markdown(
        "- Project ownership\n"
        "- Decisions and decision makers\n"
        "- Blockers and related discussions"
    )
    st.caption("Demo data currently uses synthetic source references.")

with st.form("investigation_form"):
    question = st.text_input(
        "Ask a question",
        placeholder="Why is this project blocked?",
        value="Why is this project blocked?",
    )
    submitted = st.form_submit_button(
        "Investigate",
        type="primary",
        width="stretch",
    )

if submitted:
    if not question.strip():
        st.warning("Enter a question first.")
    else:
        actual_question = question.strip()
        if selected_project.casefold() not in actual_question.casefold():
            actual_question = f"{actual_question} {selected_project}"

        try:
            result = answer_question(actual_question)
            details = investigate_company(selected_project)

            st.session_state["investigation"] = {
                "result": result,
                "details": details,
            }
        except Exception as exc:
            st.error("The investigation failed.")
            st.exception(exc)

saved = st.session_state.get("investigation")

if saved:
    result = saved["result"]
    details = saved["details"]

    st.divider()
    st.subheader("Investigation result")

    if not result.get("found"):
        st.info(result.get("answer", "No result found."))
    else:
        left, middle, right = st.columns(3)
        left.markdown("**Project**")
        left.write(details["project"])
        middle.metric("Status", details.get("status") or "Not recorded")
        right.metric(
            "Linked records",
            len(details.get("tickets", []))
            + len(details.get("messages", []))
            + len(details.get("decisions", [])),
        )

        st.markdown("### Answer")
        st.write(result["answer"])

        evidence = result.get("evidence", [])
        st.markdown(f"### Supporting evidence ({len(evidence)})")

        if not evidence:
            st.info("No supporting evidence was returned for this answer.")

        for i, item in enumerate(evidence, start=1):
            heading = item.get("claim", "Evidence item")
            with st.expander(f"{i}. {heading}", expanded=(i == 1)):
                st.write(f"**Type:** {item.get('type', 'Not specified')}")
                if item.get("id"):
                    st.write(f"**Record ID:** {item['id']}")
                st.write(f"**Source:** {item.get('source', 'Not recorded')}")

        st.markdown("### Connected knowledge graph")
        st.caption(
            "Nodes represent recorded company entities. Edges represent "
            "relationships stored in FalkorDB."
        )

        with st.expander("Connected knowledge graph", expanded=True):
            st.caption(
               "Explore the relationships between projects, people, "
               "decisions, tickets, messages, and documents."
            )
            st.graphviz_chart(make_graph(details), width="stretch")

        with st.expander("Inspect retrieved project data"):
            st.json(details)
