
import streamlit as st
import anthropic
import pdfplumber
import chromadb
import json
import re
import os
from datetime import datetime
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel
from typing import List, Optional

# ─── Page config ───────────────────────────────────────────
st.set_page_config(
    page_title="Contradiction Detector",
    page_icon="",
    layout="wide"
)

# ─── Dark theme CSS ────────────────────────────────────────
st.markdown("""
<style>
    /* Main background */
    .stApp {
        background-color: #0F1117;
        color: #E2E8F0;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1A1D27;
        border-right: 1px solid #2D3748;
    }
    
    /* Main header */
    .main-header {
        padding: 2rem 0 1rem 0;
        border-bottom: 2px solid #2D3748;
        margin-bottom: 2rem;
    }
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #F7FAFC;
        letter-spacing: -0.5px;
        margin: 0;
    }
    .main-subtitle {
        font-size: 1rem;
        color: #718096;
        margin-top: 0.4rem;
    }
    
    /* KPI cards */
    .kpi-card {
        background-color: #1A1D27;
        border-radius: 10px;
        padding: 1.2rem 1.5rem;
        border: 1px solid #2D3748;
        text-align: center;
        height: 100px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .kpi-card.total {
        border-top: 3px solid #4A90E2;
    }
    .kpi-card.critical {
        border-top: 3px solid #E53E3E;
    }
    .kpi-card.warning {
        border-top: 3px solid #D69E2E;
    }
    .kpi-card.minor {
        border-top: 3px solid #38A169;
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
        line-height: 1;
    }
    .kpi-value.total { color: #4A90E2; }
    .kpi-value.critical { color: #E53E3E; }
    .kpi-value.warning { color: #D69E2E; }
    .kpi-value.minor { color: #38A169; }
    .kpi-label {
        font-size: 0.75rem;
        color: #718096;
        margin-top: 0.4rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        white-space: nowrap;
    }
    
    /* Contradiction cards */
    .contradiction-card {
        background-color: #1A1D27;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
        border: 1px solid #2D3748;
        border-left: 4px solid #2D3748;
    }
    .contradiction-card.critical {
        border-left-color: #E53E3E;
    }
    .contradiction-card.warning {
        border-left-color: #D69E2E;
    }
    .contradiction-card.minor {
        border-left-color: #38A169;
    }
    
    /* Severity badge */
    .severity-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .severity-badge.critical {
        background-color: rgba(229, 62, 62, 0.15);
        color: #FC8181;
        border: 1px solid rgba(229, 62, 62, 0.3);
    }
    .severity-badge.warning {
        background-color: rgba(214, 158, 46, 0.15);
        color: #F6AD55;
        border: 1px solid rgba(214, 158, 46, 0.3);
    }
    .severity-badge.minor {
        background-color: rgba(56, 161, 105, 0.15);
        color: #68D391;
        border: 1px solid rgba(56, 161, 105, 0.3);
    }

    /* Document excerpt boxes */
    .doc-box {
        background-color: #0F1117;
        border: 1px solid #2D3748;
        border-radius: 6px;
        padding: 0.8rem;
        font-size: 0.85rem;
        color: #A0AEC0;
        margin-top: 0.5rem;
        line-height: 1.5;
    }
    .doc-label {
        font-size: 0.75rem;
        font-weight: 600;
        color: #4A90E2;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.3rem;
    }
    
    /* Section headers */
    .section-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #E2E8F0;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #2D3748;
        margin-bottom: 1rem;
    }
    
    /* Upload area */
    [data-testid="stFileUploader"] {
        background-color: #1A1D27;
        border: 2px dashed #2D3748;
        border-radius: 8px;
        padding: 1rem;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #4A90E2;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        width: 100%;
    }
    .stButton > button:hover {
        background-color: #357ABD;
    }

    /* Selectbox */
    .stSelectbox > div > div {
        background-color: #1A1D27;
        border-color: #2D3748;
        color: #E2E8F0;
    }
    
    /* Chat messages */
    [data-testid="stChatMessage"] {
        background-color: #1A1D27;
        border: 1px solid #2D3748;
        border-radius: 8px;
    }

    /* Divider */
    hr {
        border-color: #2D3748;
    }
    
    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 6px;
    }
    ::-webkit-scrollbar-track {
        background: #0F1117;
    }
    ::-webkit-scrollbar-thumb {
        background: #2D3748;
        border-radius: 3px;
    }
    
    /* Hide streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ─── Pydantic Models ───────────────────────────────────────
class DocumentChunk(BaseModel):
    chunk_id: str
    doc_name: str
    page_number: int
    chunk_index: int
    text: str
    char_count: int

class Contradiction(BaseModel):
    contradiction_id: str
    severity: str
    topic: str
    contradiction_type: str
    doc_a_name: str
    doc_a_page: int
    doc_a_text: str
    doc_b_name: str
    doc_b_page: int
    doc_b_text: str
    explanation: str

class ContradictionReport(BaseModel):
    generated_at: str
    documents_analysed: List[str]
    total_contradictions: int
    critical_count: int
    warning_count: int
    minor_count: int
    contradictions: List[Contradiction]

# ─── Load models ───────────────────────────────────────────
@st.cache_resource
def load_models():
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY", "")
    )
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    chroma_client = chromadb.Client()
    return client, embedding_model, chroma_client

client, embedding_model, chroma_client = load_models()

# ─── Core functions ────────────────────────────────────────
def process_pdf(file_bytes: bytes, doc_name: str,
                chunk_size: int = 500) -> List[DocumentChunk]:
    import tempfile
    chunks = []
    chunk_index = 0
    with tempfile.NamedTemporaryFile(
        suffix=".pdf", delete=False
    ) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    with pdfplumber.open(tmp_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text or len(text.strip()) < 50:
                continue
            text = re.sub(r"\s+", " ", text).strip()
            sentences = re.split(r"(?<=[.!?])\s+", text)
            current_chunk = ""
            for sentence in sentences:
                if len(current_chunk) + len(sentence) <= chunk_size:
                    current_chunk += " " + sentence
                else:
                    if current_chunk.strip():
                        chunks.append(DocumentChunk(
                            chunk_id=f"{doc_name}_p{page_num}_c{chunk_index}",
                            doc_name=doc_name,
                            page_number=page_num,
                            chunk_index=chunk_index,
                            text=current_chunk.strip(),
                            char_count=len(current_chunk.strip())
                        ))
                        chunk_index += 1
                    current_chunk = sentence
            if current_chunk.strip():
                chunks.append(DocumentChunk(
                    chunk_id=f"{doc_name}_p{page_num}_c{chunk_index}",
                    doc_name=doc_name,
                    page_number=page_num,
                    chunk_index=chunk_index,
                    text=current_chunk.strip(),
                    char_count=len(current_chunk.strip())
                ))
                chunk_index += 1
    os.unlink(tmp_path)
    return chunks

def store_chunks(chunks, collection):
    if not chunks:
        return
    texts = [c.text for c in chunks]
    ids = [c.chunk_id for c in chunks]
    metadatas = [{
        "doc_name": c.doc_name,
        "page_number": c.page_number,
        "chunk_index": c.chunk_index,
        "char_count": c.char_count
    } for c in chunks]
    batch_size = 50
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = embedding_model.encode(batch).tolist()
        all_embeddings.extend(embeddings)
    collection.add(
        documents=texts,
        embeddings=all_embeddings,
        ids=ids,
        metadatas=metadatas
    )

def find_similar_chunks(query_text, collection,
                        exclude_doc, n_results=3):
    query_embedding = embedding_model.encode(
        [query_text]
    ).tolist()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n_results * 3,
        include=["documents", "metadatas", "distances"]
    )
    filtered = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        if meta["doc_name"] != exclude_doc:
            filtered.append({
                "text": doc,
                "doc_name": meta["doc_name"],
                "page_number": meta["page_number"],
                "distance": dist
            })
        if len(filtered) >= n_results:
            break
    return filtered

def detect_contradiction(chunk_a, chunk_b):
    prompt = f"""You are an expert document analyst.
Analyse these two excerpts from different documents and 
determine if they contradict each other.

DOCUMENT A: {chunk_a["doc_name"]} (Page {chunk_a["page_number"]})
"{chunk_a["text"]}"

DOCUMENT B: {chunk_b["doc_name"]} (Page {chunk_b["page_number"]})
"{chunk_b["text"]}"

Look for contradictions including:
- Numerical: Different figures for the same metric
- Factual: Conflicting statements about facts
- Temporal: Earlier claims that conflict with later results
- Policy: Different statements about policy or strategy

Return ONLY valid JSON starting with {{ and ending with }}.
If no contradiction: {{"contradiction_found": false}}
If contradiction:
{{
  "contradiction_found": true,
  "severity": "critical/warning/minor",
  "topic": "brief topic description",
  "contradiction_type": "numerical/factual/temporal/policy",
  "explanation": "clear explanation of the contradiction"
}}"""
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    response_text = message.content[0].text.strip()
    json_start = response_text.find("{")
    if json_start == -1:
        return None
    brace_count = 0
    json_end = json_start
    for i, char in enumerate(
        response_text[json_start:], start=json_start
    ):
        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                json_end = i
                break
    try:
        result = json.loads(
            response_text[json_start:json_end + 1]
        )
    except json.JSONDecodeError:
        return None
    if not result.get("contradiction_found"):
        return None
    return result

def analyse_contradictions(all_chunks, collection):
    doc_names = list(all_chunks.keys())
    contradictions = []
    contradiction_id = 0
    checked_pairs = set()
    pairs_sent_to_claude = 0      
    pairs_with_contradictions = 0
    progress = st.progress(0)
    status = st.empty()
    total_docs = len(doc_names)
    for doc_idx, (doc_name, chunks) in enumerate(
        all_chunks.items()
    ):
        step = max(1, len(chunks) // 15)
        sampled = chunks[::step]
        status.text(
            f"Analysing {doc_name} "
            f"({len(sampled)} chunks)..."
        )
        for chunk in sampled:
            similar = find_similar_chunks(
                chunk.text, collection,
                exclude_doc=doc_name, n_results=2
            )
            for similar_chunk in similar:
                pair_key = tuple(sorted([
                    chunk.chunk_id,
                    f"{similar_chunk['doc_name']}_"
                    f"p{similar_chunk['page_number']}"
                ]))
                if pair_key in checked_pairs:
                    continue
                checked_pairs.add(pair_key)
                if similar_chunk["distance"] > 0.5:
                    continue
                pairs_sent_to_claude += 1 
                try:
                    result = detect_contradiction(
                        {
                            "text": chunk.text,
                            "doc_name": chunk.doc_name,
                            "page_number": chunk.page_number
                        },
                        similar_chunk
                    )
                except Exception:
                    result = None
                if result:
                    pairs_with_contradictions += 1
                    contradiction_id += 1
                    contradictions.append(Contradiction(
                        contradiction_id=f"C{contradiction_id:03d}",
                        severity=result["severity"],
                        topic=result["topic"],
                        contradiction_type=result[
                            "contradiction_type"
                        ],
                        doc_a_name=chunk.doc_name,
                        doc_a_page=chunk.page_number,
                        doc_a_text=chunk.text[:300],
                        doc_b_name=similar_chunk["doc_name"],
                        doc_b_page=similar_chunk["page_number"],
                        doc_b_text=similar_chunk["text"][:300],
                        explanation=result["explanation"]
                    ))
        progress.progress((doc_idx + 1) / total_docs)
    status.empty()
    progress.empty()
    print(f"\n--- Pipeline Statistics ---")
    print(f"Total chunks across all documents: {sum(len(c) for c in all_chunks.values())}")
    actual_sampled = sum(len(chunks[::max(1, len(chunks) // 15)]) for chunks in all_chunks.values())
    print(f"Total chunks sampled: {actual_sampled}")
    print(f"Total pairs sent to Claude: {pairs_sent_to_claude}")
    print(f"Pairs with contradictions: {pairs_with_contradictions}")
    if pairs_sent_to_claude > 0:
        print(f"Contradiction rate: {pairs_with_contradictions/pairs_sent_to_claude*100:.1f}%")
    return ContradictionReport(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        documents_analysed=doc_names,
        total_contradictions=len(contradictions),
        critical_count=sum(
            1 for c in contradictions if c.severity == "critical"
        ),
        warning_count=sum(
            1 for c in contradictions if c.severity == "warning"
        ),
        minor_count=sum(
            1 for c in contradictions if c.severity == "minor"
        ),
        contradictions=contradictions
    )

def chat_with_documents(question, collection, history):
    query_embedding = embedding_model.encode([question]).tolist()
    all_chunks = []
    seen_ids = set()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=8,
        include=["documents", "metadatas", "distances"]
    )
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        chunk_id = f"{meta['doc_name']}_p{meta['page_number']}"
        if chunk_id not in seen_ids and dist < 0.8:
            seen_ids.add(chunk_id)
            all_chunks.append({
                "text": doc,
                "doc_name": meta["doc_name"],
                "page_number": meta["page_number"],
                "distance": dist
            })
    all_chunks.sort(key=lambda x: x["distance"])
    top_chunks = [
        c for c in all_chunks[:6]
        if c["page_number"] > 1 and len(c["text"]) > 100
    ] or all_chunks[:6]
    context = ""
    sources = []
    for chunk in top_chunks:
        context += (
            f"\n[{chunk['doc_name']} - "
            f"Page {chunk['page_number']}]\n{chunk['text']}\n"
        )
        sources.append(
            f"{chunk['doc_name']} (Page {chunk['page_number']})"
        )
    messages = history.copy()
    messages.append({
        "role": "user",
        "content": (
            f"Answer based on these document excerpts. "
            f"Always cite the document name and page number. "
            f"If you notice contradictions between documents, "
            f"highlight them explicitly.\n\n"
            f"EXCERPTS:\n{context}\n\nQUESTION: {question}"
        )
    })
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=(
            "You are a document analyst assistant. "
            "Answer questions accurately with citations. "
            "Always reference the document name and page number. "
            "Highlight any contradictions or inconsistencies "
            "you notice across documents."
        ),
        messages=messages
    )
    answer = response.content[0].text
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})
    if len(history) > 12:
        history = history[-12:]
    return answer, list(set(sources)), history

# ─── Streamlit UI ──────────────────────────────────────────

# Sidebar
with st.sidebar:
    st.markdown(
        "<p style='font-size:1.1rem;font-weight:700;"
        "color:#E2E8F0;margin-bottom:1rem;'>"
        "Settings</p>",
        unsafe_allow_html=True
    )
    api_key = st.text_input(
        "Anthropic API Key",
        help="Enter your Anthropic API key"
    )
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key
        client = anthropic.Anthropic(api_key=api_key)
    
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(
        "<p style='font-size:0.85rem;font-weight:600;"
        "color:#A0AEC0;margin-bottom:0.8rem;'>"
        "How it works</p>",
        unsafe_allow_html=True
    )
    steps = [
        "Upload 2 or more PDF documents",
        "Click Analyse Documents",
        "Review the contradiction report",
        "Ask follow-up questions"
    ]
    for i, step in enumerate(steps, 1):
        st.markdown(
            f"<p style='font-size:0.82rem;color:#718096;"
            f"margin:0.3rem 0;'>"
            f"<span style='color:#4A90E2;font-weight:600;'>"
            f"{i}.</span> {step}</p>",
            unsafe_allow_html=True
        )
    
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(
        "<p style='font-size:0.75rem;color:#4A5568;'>"
        "Powered by Claude AI + ChromaDB RAG</p>",
        unsafe_allow_html=True
    )

# Main header
st.markdown("""
<div class="main-header">
    <p class="main-title">Multi-Document Contradiction Detector</p>
    <p class="main-subtitle">
        Upload two or more documents to automatically identify 
        contradictions, inconsistencies and conflicting information 
        across them using AI-powered analysis.
    </p>
</div>
""", unsafe_allow_html=True)

# Session state
if "report" not in st.session_state:
    st.session_state.report = None
if "collection" not in st.session_state:
    st.session_state.collection = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "messages" not in st.session_state:
    st.session_state.messages = []

# Upload section
st.markdown(
    "<p class='section-header'>Upload Documents</p>",
    unsafe_allow_html=True
)
uploaded_files = st.file_uploader(
    "Select PDF files to analyse (minimum 2)",
    type="pdf",
    accept_multiple_files=True,
    label_visibility="collapsed"
)

if uploaded_files and len(uploaded_files) >= 2:
    file_names = [f.name for f in uploaded_files]
    st.markdown(
        f"<p style='font-size:0.85rem;color:#68D391;"
        f"margin:0.5rem 0;'>"
        f"{len(uploaded_files)} documents ready: "
        f"{', '.join(file_names)}</p>",
        unsafe_allow_html=True
    )
    if st.button("Analyse Documents", type="primary"):
        with st.spinner("Processing documents..."):
            try:
                collection_name = "docs_" + str(
                    abs(hash(tuple(f.name for f in uploaded_files)))
                )[:8]
                try:
                    chroma_client.delete_collection(collection_name)
                except Exception:
                    pass
                collection = chroma_client.create_collection(
                    collection_name
                )
                all_chunks = {}
                for uploaded_file in uploaded_files:
                    doc_name = uploaded_file.name.replace(".pdf", "")
                    st.write(f"Processing {doc_name}...")
                    chunks = process_pdf(
                        uploaded_file.read(), doc_name
                    )
                    all_chunks[doc_name] = chunks
                    store_chunks(chunks, collection)
                st.session_state.collection = collection
                st.write("Running contradiction analysis...")
                report = analyse_contradictions(
                    all_chunks, collection
                )
                st.session_state.report = report
                st.session_state.chat_history = []
                st.session_state.messages = []
                st.rerun()
            except Exception as e:
                st.error(f"Error during analysis: {e}")
elif uploaded_files and len(uploaded_files) < 2:
    st.warning("Please upload at least 2 documents.")

# Report section
if st.session_state.report:
    report = st.session_state.report
    st.markdown("<hr>", unsafe_allow_html=True)

    # KPI cards
    st.markdown(
        "<p class='section-header'>Analysis Results</p>",
        unsafe_allow_html=True
    )
    col1, col2, col3, col4 = st.columns(4)
    kpis = [
        (col1, "total", report.total_contradictions,
         "Total Found"),
        (col2, "critical", report.critical_count, "Critical"),
        (col3, "warning", report.warning_count, "Warning"),
        (col4, "minor", report.minor_count, "Minor"),
    ]
    for col, cls, val, label in kpis:
        with col:
            st.markdown(
                f"<div class='kpi-card {cls}'>"
                f"<p class='kpi-value {cls}'>{val}</p>"
                f"<p class='kpi-label'>{label}</p>"
                f"</div>",
                unsafe_allow_html=True
            )

    st.markdown(
        f"<p style='font-size:0.75rem;color:#4A5568;"
        f"margin:0.8rem 0;'>"
        f"Generated {report.generated_at} — "
        f"Documents: {', '.join(report.documents_analysed)}"
        f"</p>",
        unsafe_allow_html=True
    )

    # Filter
    st.markdown("<br>", unsafe_allow_html=True)
    col_filter, col_empty = st.columns([1, 3])
    with col_filter:
        severity_filter = st.selectbox(
            "Filter by severity",
            ["All", "Critical", "Warning", "Minor"],
            label_visibility="collapsed"
        )

    filtered = report.contradictions
    if severity_filter != "All":
        filtered = [
            c for c in report.contradictions
            if c.severity == severity_filter.lower()
        ]

    st.markdown(
        f"<p style='font-size:0.82rem;color:#718096;"
        f"margin:0.5rem 0 1rem 0;'>"
        f"Showing {len(filtered)} of "
        f"{report.total_contradictions} contradictions</p>",
        unsafe_allow_html=True
    )

    # Contradiction cards
    for c in filtered:
        badge_html = (
            f"<span class='severity-badge {c.severity}'>"
            f"{c.severity.upper()}</span>"
        )
        type_html = (
            f"<span style='font-size:0.75rem;color:#718096;"
            f"margin-left:0.5rem;'>"
            f"{c.contradiction_type.upper()}</span>"
        )
        with st.expander(
            f"{c.contradiction_id} — {c.topic}"
        ):
            st.markdown(
                f"{badge_html}{type_html}",
                unsafe_allow_html=True
            )
            st.markdown("<br>", unsafe_allow_html=True)
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(
                    f"<p class='doc-label'>"
                    f"{c.doc_a_name} — Page {c.doc_a_page}"
                    f"</p>"
                    f"<div class='doc-box'>{c.doc_a_text}</div>",
                    unsafe_allow_html=True
                )
            with col_b:
                st.markdown(
                    f"<p class='doc-label'>"
                    f"{c.doc_b_name} — Page {c.doc_b_page}"
                    f"</p>"
                    f"<div class='doc-box'>{c.doc_b_text}</div>",
                    unsafe_allow_html=True
                )
            st.markdown(
                f"<p style='font-size:0.82rem;color:#A0AEC0;"
                f"margin-top:0.8rem;'>"
                f"<strong style='color:#E2E8F0;'>Analysis:</strong> "
                f"{c.explanation}</p>",
                unsafe_allow_html=True
            )

    # Download
    st.markdown("<br>", unsafe_allow_html=True)
    report_json = json.dumps(report.model_dump(), indent=2)
    st.code(report_json[:300] + "...", language="json")
    st.download_button(
        "Download Full Report (JSON)",
        data=report_json,
        file_name="contradiction_report.json",
        mime="application/json"
)

    # Chat section
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(
        "<p class='section-header'>Ask Questions</p>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='font-size:0.85rem;color:#718096;"
        "margin-bottom:1rem;'>"
        "Ask follow-up questions about the documents. "
        "Answers include source citations and will highlight "
        "contradictions where relevant.</p>",
        unsafe_allow_html=True
    )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask a question..."):
        st.session_state.messages.append(
            {"role": "user", "content": prompt}
        )
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Searching documents..."):
                answer, sources, st.session_state.chat_history = (
                    chat_with_documents(
                        prompt,
                        st.session_state.collection,
                        st.session_state.chat_history
                    )
                )
            st.markdown(answer)
            if sources:
                st.caption(
                    "Sources: " + " | ".join(sources)
                )
        st.session_state.messages.append(
            {"role": "assistant", "content": answer}
        )
