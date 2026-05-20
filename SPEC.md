# SPEC.md — Multi-Document Contradiction Detector with RAG Chatbot

## Overview

A RAG-powered application that automatically detects contradictions across multiple PDF documents and provides an AI chatbot for querying document content with source citations. Built with Python, Anthropic Claude API, ChromaDB, and Streamlit.

**Live Demo:** Tested on real DBS Group Holdings quarterly financial reports (3Q25 and 4Q25), identified between 15-20 contradictions per run including restated figures and conflicting metrics for identical reporting periods.

**GitHub:** https://github.com/eyyuen/contradiction-detector

---

## Architecture

The system has two core pipelines running on the same vector store:

**Pipeline 1 — Contradiction Detection (automated):**
```
PDF Upload → Document Processor → ChromaDB Vector Store
                                          ↓
                              Vector Similarity Search
                              (find semantically related
                               chunks across documents)
                                          ↓
                              Claude API Reasoning
                              (determine if pairs contradict)
                                          ↓
                              Contradiction Report
                              (severity classified output)
```

**Pipeline 2 — RAG Chatbot (interactive):**
```
User Question → Query Embedding → ChromaDB Retrieval
                                          ↓
                              Context Assembly
                              (top relevant chunks)
                                          ↓
                              Claude API Response
                              (answer with citations)
                                          ↓
                              Chat Interface
                              (with conversation history)
```

---

## Implementation

### 1. Document Processing and Chunking

**Library:** pdfplumber

**Strategy:** Sentence-aware chunking at 500 character limit

**How it works:**
- Extract text page by page preserving page numbers
- Split text into sentences using regex `(?<=[.!?])\s+`
- Fill chunks sentence by sentence until 500 character limit
- When next sentence would exceed limit, save current chunk and start new one
- Each chunk stores doc_name, page_number, chunk_index, text, char_count

**Why sentence-aware over fixed character chunking:**
Fixed character chunking splits mid-sentence, destroying meaning. Sentence-aware chunking preserves complete thoughts which improves both embedding quality and Claude's ability to reason about content.

**Why 500 characters:**
Small enough to be specific for precise retrieval. Large enough to contain meaningful context. Too small loses context, too large makes embeddings too general.

**Metadata stored per chunk:**
```python
{
    "doc_name": "3Q25_CFO_presentation",
    "page_number": 4,
    "chunk_index": 12,
    "char_count": 487
}
```

---

### 2. Embeddings

**Model:** sentence-transformers all-MiniLM-L6-v2

**Why this model:**
- Runs entirely locally with no API cost
- Fast inference suitable for batch processing
- 384 dimensions balances quality and storage efficiency
- Strong performance on semantic similarity tasks

**Process:**
- Chunks processed in batches of 50 to manage memory
- Each chunk converted to 384-dimension vector
- Vectors stored in ChromaDB alongside chunk text and metadata

---

### 3. Vector Storage

**Database:** ChromaDB (local)

**Why ChromaDB:**
- Runs entirely locally, no server setup required
- Simple Python API
- Supports metadata filtering — critical for excluding same-document chunks during contradiction detection
- Suitable for document-scale collections

**Collection structure:**
- One collection per analysis session
- Documents: chunk text
- Embeddings: 384-dimension vectors
- Metadatas: doc_name, page_number, chunk_index, char_count
- IDs: unique chunk identifiers (doc_name_pageN_chunkN)

---

### 4. Contradiction Detection — Prompt Engineering

**Two-stage filtering approach:**

Stage 1 — Vector similarity pre-filter:
- For each sampled chunk in Document A, find n_results=2 most similar chunks from other documents
- Only pairs with cosine distance below 0.5 proceed to Claude
- This filters approximately 90% of possible pairs that are clearly unrelated
- Prevents unnecessary API calls and cost

Stage 2 — Claude reasoning:
- Only semantically similar pairs reach Claude
- Claude determines whether similar content actually contradicts

**Why two-stage matters:**
With 224 chunks across 3 documents, the theoretical maximum cross-document pairs is in the thousands. Two-stage filtering reduces this to approximately 50-100 pairs per run — significant cost and time reduction without quality loss since unrelated pairs cannot produce meaningful contradictions.

**Contradiction detection prompt:**
```
You are an expert document analyst.
Analyse these two excerpts from different documents and 
determine if they contradict each other.

DOCUMENT A: {doc_name} (Page {page_number})
"{text}"

DOCUMENT B: {doc_name} (Page {page_number})
"{text}"

Look for contradictions including:
- Numerical: Different figures for the same metric
- Factual: Conflicting statements about facts
- Temporal: Earlier claims that conflict with later results
- Policy: Different statements about policy or strategy

Return ONLY valid JSON starting with { and ending with }.
If no contradiction: {"contradiction_found": false}
If contradiction found:
{
  "contradiction_found": true,
  "severity": "critical/warning/minor",
  "topic": "brief topic",
  "contradiction_type": "numerical/factual/temporal/policy",
  "explanation": "clear explanation"
}
```

**Prompt engineering decisions:**
- Explicit contradiction types guide Claude to reason systematically
- Severity classification produces actionable output
- Structured JSON output is machine-readable with no parsing ambiguity
- ONLY JSON instruction reduces chance of Claude adding text outside JSON
- Robust brace-counting JSON parser handles edge cases where Claude adds surrounding text

**Model:** claude-sonnet-4-5, max_tokens=2048

**Why Sonnet:** Contradiction detection requires contextual reasoning. Haiku may miss subtle patterns. Opus is unnecessarily expensive for this task. Sonnet balances reasoning quality with cost and speed.

**Why 2048 tokens:** Initial runs with 1024 tokens caused truncated JSON responses. 2048 provides sufficient headroom for full responses across all document pairs tested.

**Chunk sampling:** Maximum 15 chunks per document sampled using step = len(chunks) // 15. Balances coverage with runtime and API cost. Known limitation — contradictions in unsampled chunks will be missed. Production version would process all chunks with caching.

---

### 5. RAG Chatbot — Retrieval Strategy

**Retrieval settings:**
- n_results=8 candidates fetched per query
- Distance threshold=0.8 (wider than contradiction detection)
- Post-retrieval filter removes page 1 and chunks shorter than 100 characters

**Why wider threshold for chatbot vs contradiction detection:**
Contradiction detection needs high precision — only very similar chunks should be compared. The chatbot needs high recall — even loosely related chunks may contain the answer to a user's question.

**Why post-retrieval filtering:**
Cover pages and disclaimer pages on page 1 often have high semantic similarity to queries but contain no useful information. Filtering these improves answer quality significantly.

**Conversation history:**
Last 6 exchanges (12 messages) maintained per session. Provides context for follow-up questions without sending entire conversation history each time.

**Chatbot system prompt:**
```
You are a document analyst assistant.
Answer questions accurately with citations.
Always reference the document name and page number.
Highlight any contradictions or inconsistencies you notice.
```

**Why include contradiction highlighting in system prompt:**
The chatbot proactively surfaces issues even when not explicitly asked — making it useful for document review beyond simple Q&A.

---

### 6. Data Models (Pydantic)

All data structures use Pydantic BaseModel for typed contracts between components:

```python
class DocumentChunk(BaseModel):
    chunk_id: str
    doc_name: str
    page_number: int
    chunk_index: int
    text: str
    char_count: int

class Contradiction(BaseModel):
    contradiction_id: str
    severity: str        # critical, warning, minor
    topic: str
    contradiction_type: str  # numerical, factual, temporal, policy
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
```

**Why Pydantic:** Typed data contracts catch errors immediately at the point of creation rather than allowing bad data to propagate silently through the pipeline.

---

### 7. Error Handling

**JSON parsing:** Brace-counting parser extracts first complete JSON object even when Claude returns surrounding text. Falls back gracefully if no JSON found.

**Per-call try-catch:** Each Claude API call wrapped in try-catch. Failed calls are logged and skipped — one bad response does not crash the pipeline.

**Empty text filtering:** Pages with less than 50 characters skipped during chunking — handles blank pages and image-only pages.

**Retrieval fallback:** If post-retrieval filtering removes all candidates, falls back to unfiltered top 6 results rather than returning empty context.

**Temporary file cleanup:** PDF files written to temp storage are deleted after processing to prevent disk accumulation.

---

### 8. UI

**Framework:** Streamlit with custom dark theme

**Theme configuration:** .streamlit/config.toml sets base dark theme. Custom CSS provides colour-coded severity indicators, dark cards, and consistent styling.

**Key UI components:**
- Multi-file PDF uploader
- Real-time progress bar during analysis
- KPI cards showing total, critical, warning, minor counts
- Severity filter dropdown
- Expandable contradiction cards showing side-by-side document excerpts
- Integrated chat interface with message history
- JSON report preview

**API key handling:** Entered via sidebar input field. In production deployment the key would be managed as an environment variable and the sidebar input removed.

---

## Known Limitations and Future Improvements

**Current limitations:**
- Chunk sampling means contradictions in unsampled chunks may be missed
- Results vary between runs due to chunk sampling — the system samples a maximum of 15 chunks per document rather than processing all chunks, and different samples surface different contradiction pairs.
  Typical runs on the DBS test documents identify between 15-20 contradictions.
- Slide-based PDFs lose table and chart context during text extraction — numbers appear without labels
- Runs locally only, requires local setup

**Planned improvements:**
- Remove chunk sampling, add caching so unchanged chunks are not re-embedded on subsequent runs
- Vision model integration for slide-based PDFs to process charts and tables as images
- Contradiction confidence scoring
- Deploy to Streamlit Cloud for zero-setup access
- Support for Word documents and plain text files

---

## Tech Stack Summary

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| LLM | Anthropic Claude API (claude-sonnet-4-5) |
| Vector Store | ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| PDF Extraction | pdfplumber |
| Data Validation | Pydantic |
| UI | Streamlit |
| Styling | Custom CSS dark theme |

---

## Setup

```bash
git clone https://github.com/eyyuen/contradiction-detector.git
cd contradiction-detector
pip install -r requirements.txt
streamlit run app.py
```

Enter Anthropic API key in the sidebar when the application opens.
