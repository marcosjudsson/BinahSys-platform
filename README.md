# BinahSys — Enterprise AI Knowledge Platform

> **Binah (בִּינָה):** Hebrew for *understanding* — the capacity to connect ideas and derive insight from knowledge.

BinahSys is an open-source platform that transforms static corporate documents into a **living, conversational knowledge base**. Through configurable AI Expert Agents (Personas), it enables on-demand training, support, and knowledge retrieval — at scale, 24/7.

🔗 **[Live Demo](https://diamondone-v4-app-khq5xkcgkambe4hzm3efq9.streamlit.app/)**

---

## The Problem It Solves

In B2B and enterprise environments, critical knowledge is constantly scattered: lost in emails, locked inside a few experts' heads, buried in PDFs no one reads. The result is slow onboarding, inconsistent support, and high dependency on specific people.

BinahSys attacks this directly — not as a file repository, but as an **understanding engine**.

---

## Key Features

- **💬 Chat with Expert** — Conversational interface powered by configurable AI Personas with memory and context
- **🧠 Persona Manager** — Create, configure and version AI agents with custom prompts, knowledge sources, and LLM model selection (Gemini 2.0 Flash/Pro)
- **📚 Knowledge Manager** — Upload documents (PDF, DOCX, TXT) and ingest them into the RAG pipeline; supports both local and cloud backends
- **📊 Analytics Dashboard** — Monitor usage, top queries, and knowledge gaps over time
- **👥 User & Profile Manager** — Multi-user access control with role-based profiles
- **✍️ SEO Agent** — AI-powered blog content optimization agent
- **📄 Document Factory** — Export AI-generated responses as formatted `.docx` documents

---

## Architecture

BinahSys implements a **Hybrid RAG** strategy with two backends:

```
User → Streamlit UI → Chat Logic
                          │
              ┌───────────┴───────────┐
              │                       │
        [Local Mode]           [Cloud Mode]
        LangChain + FAISS      Vertex AI RAG Engine
        HuggingFace Embeddings    (europe-west4)
        (dev / lightweight)           │
                                  Gemini LLM
                                  (us-central1)
```

### Hybrid RAG Decision Flow

Each Persona can be configured with a `google_corpus_id`. If set:
- Routes queries to **Vertex AI RAG Engine** (cloud, with source citations)
- Ignores local FAISS index

If not set:
- Uses **LangChain + FAISS** locally (fast, zero cloud cost)

### Automated Ingestion Pipeline (Serverless)

For production environments, BinahSys includes a fully automated document ingestion pipeline:

```
Google Drive (PDF drop)
        │
  Google Apps Script (every 5 min)
        │
  Cloud Storage Inbox (southamerica-east1)
        │
  Eventarc Trigger (cross-region)
        │
  Cloud Run Service (europe-west4)
        │  ├── Move file to "processed" bucket
        │  └── Upload to Vertex AI RAG Corpus
        │
  Vertex AI RAG Engine (indexed, queryable)
```

**Why cross-region?** Data residency in Brazil/Europe (compliance), LLM inference in US (access to latest Gemini models not yet available in EU).

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Streamlit (multi-page) |
| **Backend** | Python 3, LangChain |
| **Local RAG** | FAISS, HuggingFace Embeddings (`paraphrase-multilingual-MiniLM-L12-v2`) |
| **Cloud RAG** | Google Vertex AI RAG Engine |
| **LLM** | Google Gemini 2.0 Flash / Pro (via Vertex AI) |
| **Database** | PostgreSQL (users/personas) + SQLite (local dev) |
| **Ingestion Pipeline** | Google Apps Script + Cloud Storage + Eventarc + Cloud Run |
| **CI/CD** | GitHub Actions (scheduled ingestion) |
| **Document Export** | python-docx (Document Factory) |
| **Deployment** | Streamlit Cloud |

---

## Project Structure

```
binahsys/
├── app.py                  # Entry point + auth
├── pages/
│   ├── 1_Chat.py           # Expert chat interface
│   ├── 2_Personas.py       # Persona manager
│   ├── 3_Knowledge.py      # Document ingestion
│   ├── 4_Dashboard.py      # Analytics
│   ├── 5_Users.py          # User management
│   └── 6_SEO_Agent.py      # SEO content agent
├── src/
│   ├── chat_logic.py       # RAG chain orchestration
│   ├── google_rag_engine.py # Vertex AI integration
│   └── document_factory.py # .docx export
├── docs/                   # Architecture & decision records
│   ├── ARCHITECTURE.md
│   ├── ADR.md
│   └── ROADMAP.md
└── tests/                  # pytest test suite
```

---

## Getting Started

### Prerequisites
- Python 3.10+
- Google Cloud account (for Vertex AI mode) OR just run locally with FAISS

### Local Setup (FAISS mode — no cloud required)

```bash
git clone https://github.com/marcosjudsson/diamondone-v4-app
cd diamondone-v4-app
pip install -r requirements.txt
```

Create `.env`:
```env
GEMINI_API_KEY=your_gemini_api_key
```

Run:
```bash
streamlit run app.py
```

### Cloud Setup (Vertex AI mode)
Requires a Google Cloud project with Vertex AI API enabled and a Service Account key.

```env
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
GCP_PROJECT_ID=your-project-id
VERTEX_REGION=europe-west4
```

See `docs/ARCHITECTURE.md` for full cloud setup guide.

---

## Roadmap

- [x] Multi-Persona RAG chat with conversation memory
- [x] Hybrid RAG (Local FAISS + Vertex AI)
- [x] Automated serverless ingestion pipeline
- [x] User management with role-based profiles
- [x] Analytics dashboard
- [x] Document export (.docx)
- [ ] Google Drive sync (auto-update knowledge base)
- [ ] Long-term memory (agent learns from conversations)
- [ ] Multi-agent workflows (Personas collaborate on complex tasks)
- [ ] Vertex AI integration via managed corpus (production-grade)

---

## Design Decisions

Full decision log in [`docs/ADR.md`](docs/ADR.md). Key choices:

- **Why Streamlit?** Fastest path to a production-quality UI without frontend overhead. Enables rapid iteration with non-technical stakeholders.
- **Why hybrid RAG?** Local FAISS for development speed and zero cost; Vertex AI for production scale, managed infrastructure, and source citations.
- **Why cross-region architecture?** European data residency for compliance, US inference region for access to latest Gemini capabilities.
- **Why Gemini?** Best-in-class multilingual performance for Portuguese/English mixed enterprise content.

---

## Screenshots

| Persona Manager | Chat Interface |
|---|---|
| ![Persona Manager](docs/screenshots/persona-manager.png) | ![Chat](docs/screenshots/chat.png) |

---

## Author

**Marcos Judsson** — AI Engineer & B2B Solutions Consultant

Combining 8+ years of enterprise B2B experience with applied AI engineering. BinahSys was built to solve real knowledge management problems observed across industrial and ERP environments.

- 🔗 [LinkedIn](https://www.linkedin.com/in/marcosjudsson/)
- 🐙 [GitHub](https://github.com/marcosjudsson)

---

## License

MIT — feel free to use, fork, and build on top of BinahSys.
