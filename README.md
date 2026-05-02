# Multi-Document Contradiction Detector

An AI-powered tool that automatically detects contradictions, inconsistencies and conflicting information across multiple documents using RAG (Retrieval-Augmented Generation) and the Claude API.

## What It Does

Most document review processes rely on manual comparison — slow, error-prone, and impractical at scale. This tool automates the process:

1. Upload 2 or more PDF documents
2. The system chunks and embeds all documents into a local vector store
3. For each chunk, it finds semantically similar content in other documents
4. Claude AI reasons about whether the paired chunks contradict each other
5. A structured report is generated with severity ratings and explanations
6. A RAG-powered chatbot allows follow-up questions with source citations

## Demo

Tested on DBS Group Holdings quarterly financial reports (3Q25 and 4Q25), the system identified **19 contradictions** including:

- Historical figures restated without disclosure between quarterly reports
- Net Interest Income figures differing for the same period across reports
- Deposit and loan balances showing material discrepancies for identical dates
- Capital ratio figures inconsistent between consecutive presentations

These are real discrepancies in publicly available financial documents — demonstrating the system works on complex, real-world data.

## System Architecture
PDF Upload (Streamlit UI)
│
▼
Document Processor

Text extraction with pdfplumber
Sentence-aware chunking with page tracking
Metadata preservation (doc name, page number)
│
▼
Vector Store (ChromaDB + sentence-transformers)
Local embeddings using all-MiniLM-L6-v2
Semantic similarity search across documents
Filtered retrieval by source document
│
▼
Contradiction Engine (Claude API)
Paired chunk comparison across documents
Structured JSON output with severity rating
Four contradiction types: numerical, factual, temporal, policy
│
▼
Report Generator
Severity classification: Critical / Warning / Minor
Source citations with document name and page number
Downloadable JSON report
│
▼
RAG Chatbot (Claude API + ChromaDB)
Semantic retrieval for relevant context
Conversation history maintained
Answers with source citations

## Tech Stack

| Tool | Purpose |
|---|---|
| Python | Core language |
| Streamlit | Web UI with dark theme |
| Anthropic Claude API | Contradiction detection + chatbot |
| ChromaDB | Local vector store |
| sentence-transformers | Document embeddings (all-MiniLM-L6-v2) |
| pdfplumber | PDF text extraction |
| Pydantic | Typed data models |

## Project Structure
contradiction_detector/
│
├── app.py                    ← Streamlit application
├── requirements.txt
├── .env.example
├── .streamlit/
│   └── config.toml           ← Dark theme configuration
└── sample_docs/              ← DBS quarterly reports (demo data)

## Setup and Running Locally

```bash
# Clone the repository
git clone https://github.com/eyyuen/contradiction-detector.git
cd contradiction-detector

# Install dependencies
pip install -r requirements.txt

# Set your Anthropic API key
export ANTHROPIC_API_KEY=your-api-key-here

# Run the application
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## How to Use

1. Enter your Anthropic API key in the sidebar
2. Upload 2 or more PDF documents using the file uploader
3. Click **Analyse Documents** and wait 3-5 minutes
4. Review the contradiction report — expand each item for details
5. Use the chat interface to ask follow-up questions

## Key Design Decisions

**Why vector similarity before Claude?**
Sending every possible document pair to Claude would be extremely expensive. Instead, ChromaDB first finds semantically similar chunk pairs — only chunks discussing the same topic get sent to Claude for contradiction analysis. This reduces API calls by ~90% while maintaining accuracy.

**Why sentence-aware chunking?**
Simple character-based chunking splits sentences mid-way, destroying meaning. Sentence-aware chunking preserves complete thoughts while respecting a size limit — improving both embedding quality and Claude's ability to reason about the content.

**Why local embeddings instead of API embeddings?**
sentence-transformers runs entirely locally with no API cost. For a tool that may process hundreds of chunks per run, this keeps operating costs low while maintaining good retrieval quality.

**Why Pydantic models?**
Typed data contracts between pipeline stages prevent silent failures. If Claude returns unexpected output structure, the system fails loudly with a clear error rather than silently producing wrong results.

## Limitations and Future Improvements

- Extraction quality depends on PDF structure — slide-based PDFs lose table context during text extraction
- Similarity threshold (0.5) may miss some contradictions in loosely worded documents — tunable per use case
- Currently runs locally only — Streamlit Cloud deployment planned
- Future: support for Word documents and plain text files
- Future: contradiction confidence scoring
- Future: side-by-side document diff view

## Author

Yuen Wei Ling — [GitHub](https://github.com/eyyuen) | [LinkedIn](https://www.linkedin.com/in/wei-ling-y-73b88122a/) | Singapore
