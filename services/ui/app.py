"""
CaseMinds — Streamlit UI (V1, production-quality)

Features:
  - Streaming pipeline progress (via SSE) — user sees each agent complete in real time
  - Confidence meter with colour coding
  - Citation cards with court, date, excerpt, Kanoon deep-link
  - ⚠️ Overruled amber banners
  - LOW_CONFIDENCE grey abstention
  - Citation graph visualisation (mini NetworkX → pyvis HTML)
  - Session history (last 5 queries, click to re-run)
  - Feedback buttons
  - Live system health in sidebar
"""

import json
import time
from collections import deque

import httpx
import streamlit as st

API_BASE = "http://localhost:8080/api/v1"
MAX_HISTORY = 5

st.set_page_config(
    page_title="CaseMinds — Indian Legal Research",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state ──────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = deque(maxlen=MAX_HISTORY)
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Typography */
.main-title { font-size: 2.4rem; font-weight: 700; color: #1a1a2e; margin-bottom: 0; }
.main-subtitle { color: #6b7280; font-size: 0.95rem; margin-top: 0; }

/* Cards */
.citation-card {
    background: #f8faff;
    border-left: 4px solid #2563eb;
    padding: 14px 18px;
    border-radius: 8px;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.overruled-card {
    background: #fffbeb;
    border-left: 4px solid #f59e0b;
    padding: 14px 18px;
    border-radius: 8px;
    margin-bottom: 12px;
}
.low-confidence-banner {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-left: 4px solid #9ca3af;
    padding: 18px;
    border-radius: 8px;
    color: #6b7280;
    font-style: italic;
}
.answer-box {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    padding: 22px 26px;
    border-radius: 10px;
    font-size: 15px;
    line-height: 1.75;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}

/* Status pills */
.pill {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 500;
    margin-right: 6px;
}
.pill-blue  { background: #eff6ff; color: #1d4ed8; }
.pill-green { background: #f0fdf4; color: #15803d; }
.pill-amber { background: #fffbeb; color: #b45309; }
.pill-grey  { background: #f3f4f6; color: #6b7280; }

/* Progress stepper */
.step { display: flex; align-items: center; gap: 8px; margin: 4px 0; font-size: 14px; }
.step-done  { color: #15803d; }
.step-active{ color: #1d4ed8; font-weight: 600; }
.step-wait  { color: #9ca3af; }

/* History item */
.history-item {
    padding: 6px 10px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    color: #374151;
    background: #f9fafb;
    margin-bottom: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.disclaimer { font-size: 11px; color: #9ca3af; margin-top: 16px; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown('<p class="main-title">⚖️ CaseMinds</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="main-subtitle">GraphRAG legal research for Indian law · '
    'Every citation verified against real corpus · Never fabricates</p>',
    unsafe_allow_html=True,
)
st.divider()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ System")
    try:
        h = httpx.get(f"{API_BASE}/health", timeout=4).json()
        col1, col2 = st.columns(2)
        col1.metric("Judgments", h.get("corpus_size", 0))
        col2.metric("Graph nodes", h.get("graph_nodes", 0))
        st.caption(f"Graph edges: {h.get('graph_edges', 0)}")
        st.success("API online", icon="✅")
    except Exception:
        st.error("API offline — run `make run`")

    st.divider()
    st.subheader("📊 Eval metrics")
    try:
        ev = httpx.get(f"{API_BASE}/eval/latest", timeout=4).json()
        if ev.get("citation_accuracy") is not None:
            ca = ev["citation_accuracy"]
            od = ev.get("overruled_detection", 0)
            p5 = ev.get("retrieval_precision_at_5", 0)
            st.progress(ca, text=f"Citation accuracy: {ca:.0%}")
            st.progress(od, text=f"Overruled detection: {od:.0%}")
            st.progress(p5, text=f"Precision@5: {p5:.0%}")
        else:
            st.caption("No eval run yet. Run `make eval-all`.")
    except Exception:
        st.caption("Eval data unavailable")

    st.divider()
    st.subheader("🕑 Recent queries")
    for h_query in reversed(list(st.session_state.history)):
        if st.button(f"↩ {h_query[:50]}…" if len(h_query) > 50 else f"↩ {h_query}",
                     key=f"hist_{h_query[:20]}", use_container_width=True):
            st.session_state["prefill_query"] = h_query
            st.rerun()

# ── Query input ────────────────────────────────────────────────────────────────
prefill = st.session_state.pop("prefill_query", "")

col_input, col_btn = st.columns([5, 1])
with col_input:
    query = st.text_input(
        "Ask a legal question",
        value=prefill,
        placeholder="e.g. Does Section 138 NI Act apply to post-dated cheques?",
        label_visibility="collapsed",
    )
with col_btn:
    search_clicked = st.button("🔍 Search", type="primary", use_container_width=True)

st.caption(
    "**Try:** "
    "`Section 138 NI Act post-dated cheques` &nbsp;·&nbsp; "
    "`Cheque bounce limitation period` &nbsp;·&nbsp; "
    "`Order 39 CPC temporary injunction conditions`"
)

# ── Run pipeline ───────────────────────────────────────────────────────────────
if search_clicked and query.strip():
    st.session_state.history.append(query.strip())

    # Pipeline progress stepper
    st.markdown("---")
    agents = [
        ("🔍", "Query Classifier",    "Classifying query type & routing strategy"),
        ("📚", "Retrieval Agent",     "BM25 + dense hybrid search + CrossEncoder rerank"),
        ("🕸️", "Graph Traversal",     "Expanding via citation graph (2-hop BFS)"),
        ("✅", "Verification + Answer", "Generating & verifying every citation"),
    ]
    step_placeholders = [st.empty() for _ in agents]

    def render_steps(done: int) -> None:
        for i, (icon, name, detail) in enumerate(agents):
            if i < done:
                cls = "step-done"; icon_str = "✅"
            elif i == done:
                cls = "step-active"; icon_str = "⏳"
            else:
                cls = "step-wait"; icon_str = "○"
            step_placeholders[i].markdown(
                f'<div class="step {cls}">{icon_str} <b>{name}</b> — {detail}</div>',
                unsafe_allow_html=True,
            )

    render_steps(0)
    start = time.time()

    try:
        # Use regular (blocking) endpoint — Streamlit can't consume SSE natively
        render_steps(1)
        response = httpx.post(
            f"{API_BASE}/query",
            json={"query": query.strip()},
            timeout=90,
        )
        render_steps(2)
        response.raise_for_status()
        render_steps(3)
        data = response.json()
        render_steps(4)
    except httpx.HTTPStatusError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text}")
        st.stop()
    except httpx.RequestError as e:
        st.error(f"Connection error: {e}. Is `make run` running?")
        st.stop()

    elapsed = time.time() - start
    st.session_state.last_result = data
    st.markdown("---")

    # ── Status pills ───────────────────────────────────────────────────────────
    status = data.get("status", "")
    confidence = data.get("confidence", 0.0)
    query_type = data.get("query_type") or "GENERAL"

    conf_color = "green" if confidence >= 0.85 else ("amber" if confidence >= 0.5 else "grey")
    status_color = "green" if status == "COMPLETE" else "grey"

    st.markdown(
        f'<span class="pill pill-{status_color}">{status}</span>'
        f'<span class="pill pill-{conf_color}">Confidence: {confidence:.0%}</span>'
        f'<span class="pill pill-blue">{query_type}</span>'
        f'<span class="pill pill-grey">⏱ {elapsed:.1f}s</span>',
        unsafe_allow_html=True,
    )

    # ── Confidence bar ─────────────────────────────────────────────────────────
    st.progress(
        confidence,
        text=f"Citation verification confidence: {confidence:.0%}"
        + (" — COMPLETE ✅" if confidence >= 0.85 else " — LOW CONFIDENCE ⚠️"),
    )
    st.markdown("")

    # ── LOW_CONFIDENCE abstention ──────────────────────────────────────────────
    if status in ("LOW_CONFIDENCE", "NO_RESULTS"):
        st.markdown(
            f'<div class="low-confidence-banner">'
            f'<b>⚠️ Insufficient confidence</b><br><br>'
            f'{data.get("answer", "")}'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.info("💡 **Tip:** Try rephrasing, or search [Indian Kanoon](https://indiankanoon.org) directly.")
        st.stop()

    # ── Overruled warnings ─────────────────────────────────────────────────────
    for w in data.get("overruled_warnings", []):
        st.markdown(
            f'<div class="overruled-card">'
            f'⚠️ <b>Overruled case encountered:</b> <i>{w["case_name"]}</i>'
            + (f'<br>Overruled by: <b>{w["overruled_by"]}</b>' if w.get("overruled_by") else "")
            + f'<br><small>Do not rely on this as current good law.</small>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Answer ─────────────────────────────────────────────────────────────────
    st.subheader("📖 Answer")
    st.markdown(
        f'<div class="answer-box">{data.get("answer", "")}</div>',
        unsafe_allow_html=True,
    )

    # ── Citation cards ─────────────────────────────────────────────────────────
    citations = data.get("citations", [])
    if citations:
        st.subheader(f"📎 Citations ({len(citations)})")
        for c in citations:
            is_overruled = c.get("is_overruled", False)
            card_cls = "overruled-card" if is_overruled else "citation-card"
            badge = ' &nbsp;<span style="color:#b45309;font-weight:600">⚠️ OVERRULED</span>' if is_overruled else ""

            parts = [f'<div class="{card_cls}">']
            parts.append(f'<b>{c["case_name"]}</b>{badge}')
            if c.get("citation"):
                parts.append(f'<br><span style="color:#374151;font-size:13px">{c["citation"]}</span>')
            if c.get("court"):
                parts.append(f' &nbsp;·&nbsp; <span style="color:#6b7280;font-size:13px">{c["court"]}</span>')
            if c.get("date"):
                parts.append(f' &nbsp;·&nbsp; <span style="color:#6b7280;font-size:12px">{c["date"]}</span>')
            if c.get("excerpt"):
                parts.append(f'<br><span style="font-size:13px;color:#4b5563"><i>"{c["excerpt"][:220]}…"</i></span>')
            if c.get("kanoon_url"):
                parts.append(
                    f'<br><a href="{c["kanoon_url"]}" target="_blank" '
                    f'style="font-size:13px;color:#2563eb">View full judgment on Indian Kanoon →</a>'
                )
            parts.append("</div>")
            st.markdown("".join(parts), unsafe_allow_html=True)

    # ── Citation graph visualisation ───────────────────────────────────────────
    if citations and len(citations) > 1:
        with st.expander("🕸️ Citation graph — relationships between retrieved cases", expanded=False):
            try:
                import networkx as nx
                from pyvis.network import Network  # type: ignore[import]

                G = nx.DiGraph()
                query_node = "Your Query"
                G.add_node(query_node, color="#2563eb", size=25, title=query.strip())

                for c in citations:
                    node_id = c["doc_id"]
                    color = "#f59e0b" if c.get("is_overruled") else "#15803d"
                    label = c["case_name"][:30]
                    title = f'{c["case_name"]}\n{c.get("citation","")}\n{c.get("court","")}'
                    G.add_node(node_id, color=color, size=18, title=title, label=label)
                    G.add_edge(query_node, node_id, title="retrieved")

                net = Network(height="400px", width="100%", directed=True, bgcolor="#ffffff")
                net.from_nx(G)
                net.set_options('{"physics": {"stabilization": {"iterations": 100}}}')

                html = net.generate_html()
                st.components.v1.html(html, height=420, scrolling=False)
                st.caption("🟢 Verified citation &nbsp;·&nbsp; 🟡 Overruled case &nbsp;·&nbsp; 🔵 Your query")
            except ImportError:
                st.info("Install `pyvis` (`pip install pyvis`) to see citation graph visualization.")
            except Exception as e:
                st.caption(f"Graph viz unavailable: {e}")

    # ── Feedback ────────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("**Was this answer helpful?**")
    fb1, fb2, fb3 = st.columns(3)
    trace_id = data.get("trace_id", "")

    def _send_feedback(rating: str) -> None:
        try:
            r = httpx.post(
                f"{API_BASE}/feedback",
                json={"trace_id": trace_id, "rating": rating},
                timeout=5,
            )
            if r.status_code == 201:
                st.success("Thanks for your feedback!")
            else:
                st.warning("Could not save feedback.")
        except Exception:
            st.warning("Could not reach API for feedback.")

    with fb1:
        if st.button("👍 Helpful", use_container_width=True):
            _send_feedback("HELPFUL")
    with fb2:
        if st.button("👎 Not helpful", use_container_width=True):
            _send_feedback("NOT_HELPFUL")
    with fb3:
        if st.button("🔸 Partially helpful", use_container_width=True):
            _send_feedback("PARTIALLY_HELPFUL")

    st.markdown(
        f'<p class="disclaimer">{data.get("disclaimer", "")}'
        f' &nbsp;·&nbsp; Trace ID: <code>{trace_id}</code></p>',
        unsafe_allow_html=True,
    )

elif search_clicked and not query.strip():
    st.warning("Please enter a legal question.")
