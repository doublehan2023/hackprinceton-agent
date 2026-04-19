# ACTA — AI Contract Analysis

ACTA is an AI-powered contract review platform that automatically analyzes legal contracts to identify risks, extract key clauses, check compliance, and suggest improvements. It features a multi-agent LangGraph pipeline backed by OpenAI or K2 AI reasoning models, with a Next.js frontend and FastAPI backend.

## Features

- Upload contracts in PDF, DOCX, or TXT format.
- Automated clause extraction and risk scoring.
- Compliance checking and improvement suggestions.
- Document redlining with proposed changes.
- Interactive chat Q&A about any uploaded contract.
- Contract rewriting to standardized ACTA format.

## Prerequisites

- Python 3.10+
- Node.js 18+
- An OpenAI API key **or** a K2 API key

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/doublehan2023/hackprinceton-agent.git
cd hackprinceton-agent
```

### 2. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your API credentials:

```env
# Use OpenAI (required if not using K2)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

# Use K2 Think reasoning model (optional — takes priority over OpenAI if set)
K2_API_KEY=your_k2_api_key_here
K2_MODEL=MBZUAI-IFM/K2-Think-v2
```

### 3. Set up the Python backend

```bash
cd python
python -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Set up the frontend

```bash
cd ../frontend
npm install
```

## Running the App

Open two terminal windows from the project root.

**Terminal 1 — Backend:**

```bash
cd python
source venv/bin/activate      # On Windows: venv\Scripts\activate
python -m src.api.main
```

The API will be available at `http://localhost:8000`.

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000` in your browser.

## Running Tests

```bash
cd python
source venv/bin/activate
pytest
```

## Project Structure

```
hackprinceton-agent/
├── frontend/          # Next.js 16 + React 19 + Tailwind CSS frontend
├── python/            # FastAPI backend
│   ├── src/
│   │   ├── agents/    # LangGraph agent nodes (clause extraction, risk, compliance)
│   │   ├── api/       # FastAPI routes and schemas
│   │   ├── parsers/   # PDF/DOCX/TXT document parsers
│   │   ├── pipeline/  # LangGraph workflow graph
│   │   └── services/  # Review, chat, and rewrite orchestration
│   └── tests/
├── uploads/           # Uploaded contract files
└── .env.example       # Environment variable template
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload a contract file |
| `POST` | `/api/analyze` | Analyze an uploaded contract |
| `POST` | `/api/v1/review` | Review inline contract text |
| `POST` | `/api/acta-rewrite` | Rewrite contract to ACTA format |
| `POST` | `/api/chat` | Chat Q&A about a contract |
| `GET` | `/api/health` | Health check |
