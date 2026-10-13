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

    def add_node(node_id, label, shape="box", fillcolor=None):
        color_attr = f", fillcolor={json.dumps(fillcolor)}" if fillcolor else ""
        nodes.append(
            f"{node_id} [label={json.dumps(str(label))}, "
            f"shape={shape}{color_attr}];"
        )

    def add_edge(source, target, relationship):
        edges.append(
            f"{source} -> {target} "
            f"[label={json.dumps(relationship)}];"
        )

    add_node("project", data["project"], "doublecircle", "#DCEBFF")

    for i, owner in enumerate(data.get("owners", [])):
        node_id = f"owner_{i}"
        add_node(node_id, f"{owner['name']}\n{owner.get('role') or 'Person'}", fillcolor="#DCFCE7")
        add_edge("project", node_id, "OWNED_BY")

    # Uploaded documents are linked directly to their project.
    for i, document in enumerate(data.get("uploaded_documents", [])):
        node_id = f"uploaded_document_{i}"
        filename = document.get("filename", "Uploaded document")
        pages = document.get("pages")
        label = filename
        if pages is not None:
            label += f"\n{pages} page(s)"
        add_node(node_id, label, "note", "#CCFBF1")
        add_edge(node_id, "project", "ABOUT")

    for i, ticket in enumerate(data.get("tickets", [])):
        node_id = f"ticket_{i}"
        add_node(node_id, f"{ticket['title']}\n{ticket['status']}")
        add_edge(node_id, "project", "BLOCKS")

    for i, message in enumerate(data.get("messages", [])):
        node_id = f"message_{i}"
        add_node(node_id, message["content"], fillcolor="#F3E8FF")
        add_edge(node_id, "project", "DISCUSSES")

    for i, decision in enumerate(data.get("decisions", [])):
        decision_id = f"decision_{i}"
        add_node(
            decision_id,
            f"{decision['title']}\n{decision['status']}",
            "diamond",
            "#FFE4E6",
        )
        add_edge(decision_id, "project", "AFFECTS")

        for j, person in enumerate(decision.get("decision_makers", [])):
            person_id = f"maker_{i}_{j}"
            add_node(person_id, person, "ellipse", "#DCFCE7")
            add_edge(person_id, decision_id, "MADE")

        for j, person in enumerate(decision.get("responsible_people", [])):
            person_id = f"responsible_{i}_{j}"
            add_node(person_id, person, "ellipse", "#DCFCE7")
            add_edge(person_id, decision_id, "RESPONSIBLE_FOR")

        for j, document in enumerate(decision.get("documents", [])):
            document_id = f"document_{i}_{j}"
            add_node(document_id, document["title"], fillcolor="#CCFBF1")
            add_edge(document_id, decision_id, "RECORDS")

    return (
        "digraph Knowlattice {\n"
        '  graph [label="Knowlattice", labelloc="t", fontsize=18, '
        'fontname="sans-serif", pad="0.3", nodesep="0.5", ranksep="0.8"];\n'
        "  rankdir=LR;\n"
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
            evidence_type = item.get("type", "Evidence item")
            filename = item.get("filename")
            page = item.get("page")

            if evidence_type == "uploaded_document":
                heading = f"Document: {filename or 'Uploaded file'}"
                if page is not None:
                    heading += f" — page {page}"
            else:
                heading = item.get("claim", "Evidence item")
                heading = " ".join(heading.split())
                if len(heading) > 100:
                    heading = heading[:97].rsplit(" ", 1)[0] + "..."

            with st.expander(f"{i}. {heading}", expanded=(i == 1)):
                st.caption(f"Evidence type: {evidence_type.replace('_', ' ').title()}")

                if filename:
                    st.write(f"**Filename:** {filename}")
                if page is not None:
                    st.write(f"**Page:** {page}")
                if item.get("id"):
                    st.write(f"**Record ID:** {item['id']}")

                st.write(item.get("claim", "No excerpt available."))

                matched_terms = item.get("matched_terms", [])
                if matched_terms:
                    st.caption("Matched terms: " + ", ".join(matched_terms))

                st.caption(f"Source: {item.get('source', 'Not recorded')}")

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
        st.markdown(
            """
            **Graph legend**
            <span style="background:#DCEBFF;padding:4px 8px;border-radius:4px">Project</span>
            <span style="background:#DCFCE7;padding:4px 8px;border-radius:4px">People</span>
            <span style="background:#FEF3C7;padding:4px 8px;border-radius:4px">Tickets</span>
            <span style="background:#F3E8FF;padding:4px 8px;border-radius:4px">Messages</span>
            <span style="background:#FFE4E6;padding:4px 8px;border-radius:4px">Decisions</span>
            <span style="background:#CCFBF1;padding:4px 8px;border-radius:4px">Documents</span>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("Inspect retrieved project data"):
            st.json(details)


# Document ingestion
st.divider()
st.header("Document ingestion")
st.caption(
    "Upload a PDF or TXT file and associate it with a project. "
    "The extracted text and source metadata will be stored in FalkorDB."
)

from src.ingest_documents import ingest_document, search_document_chunks

with st.expander("Upload a company document", expanded=False):
    with st.form("document_ingestion_form", clear_on_submit=False):
        uploaded_file = st.file_uploader(
            "Choose a PDF or TXT file",
            type=["pdf", "txt"],
        )
        target_project = st.selectbox(
            "Associate document with project",
            projects,
            key="ingestion_project",
        )
        ingest_submitted = st.form_submit_button(
            "Ingest document",
            type="primary",
            width="stretch",
        )

    if ingest_submitted:
        if uploaded_file is None:
            st.warning("Choose a PDF or TXT file first.")
        else:
            try:
                outcome = ingest_document(
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    target_project,
                )
                if outcome["status"] == "duplicate":
                    st.info(outcome["message"])
                else:
                    st.success(
                        f"Ingested {outcome['filename']}: "
                        f"{outcome['pages']} page(s), "
                        f"{outcome['characters']} characters."
                    )
                    st.code(outcome["source"])
            except Exception as exc:
                st.error(f"Document ingestion failed: {exc}")

with st.expander("Search ingested documents", expanded=False):
    search_project = st.selectbox(
        "Project to search",
        projects,
        key="document_search_project",
    )
    search_terms = st.text_input(
        "Search terms",
        placeholder="e.g. schema validation",
        key="document_search_terms",
    )

    if st.button("Search documents"):
        if not search_terms.strip():
            st.warning("Enter one or more search terms.")
        else:
            try:
                matches = search_document_chunks(
                    search_project,
                    search_terms,
                )
                if not matches:
                    st.info("No matching document chunks found.")
                else:
                    st.success(f"Found {len(matches)} matching page(s).")
                    for match in matches:
                        st.markdown(
                            f"**{match['filename']} — page {match['page']}**"
                        )
                        st.caption(f"Source: {match['source']}")
                        st.write(match["text"])
                        st.divider()
            except Exception as exc:
                st.error(f"Document search failed: {exc}")
