# AURA - AI-Powered Article Summarization & Brainstorming Platform

AURA is a complete, production-ready web application that transforms standard article reading into an interactive learning experience. Paste any article URL, and AURA will scrape it, clean the content, generate extractive summaries (using TextRank) and abstractive summaries (using Google Gemini API), calculate a wide range of advanced metadata insights (key takeaways, pros & cons, timeline, MCQs, flashcards), and launch a grounded chat session (RAG) using a local FAISS vector database.

---

## Features

- **Boilerplate-Free Extraction**: Primary extraction using `trafilatura` with fallbacks to `newspaper3k` and `BeautifulSoup4` to guarantee clean content with navigation links, sidebars, and ads stripped.
- **Text Normalization & Tokenization**: Sentences are split and cleaned using regex and `spaCy` NLP pipelines.
- **Dual Summarization**:
  - **Extractive**: Sumy (TextRank) selects the top 5–10 sentences preserving original wording.
  - **Abstractive**: Google Gemini API writes 2–5 cohesive, human-grade explanatory paragraphs.
- **Gemini-Powered Structured Insights**: Retrieves pros, cons, timelines, statistics, quotes, hashtags, difficulty, and sentiment in a single structured API request.
- **Interactive Study Materials**:
  - Accordion Frequently Asked Questions (FAQs).
  - Interactive 3D flipping Flashcards.
  - Multiple Choice Questions (MCQs) with instant visual feedback.
- **Grounded Chat Workspace (RAG)**: Ask questions about the article context. Responses are grounded strictly in semantic text chunks matched from the local FAISS index (`sentence-transformers/all-MiniLM-L6-v2` embeddings).
- **Stateless Chat Memory**: Chat session maintains memory of the last 10 messages.
- **Slash Commands**: Quick terminal commands inside the chat to instantly print summaries, MCQs, flashcards, entities, and timelines.
- **Multi-Format Export**: Download complete study reports in PDF, Markdown, Plain Text, or JSON.
- **Premium Glassmorphic Design**: Vibrant dark/light themes built with Vanilla CSS variables and micro-animations.

---

## Project Structure

```
AI-Article-Summarizer/
├── api/
│   ├── chat.py           # /chat endpoint (RAG + slash commands)
│   └── summarize.py      # /analyze, /history, /article, /export, /health endpoints
├── backend/
│   └── main.py           # FastAPI entrypoint & static frontend server
├── database/
│   └── db.json           # File-based JSON database (article metadata history)
├── frontend/
│   ├── index.html        # Glassmorphic user interface structure
│   ├── script.js         # Frontend controller and API fetch integration
│   └── style.css         # Styling system (layouts, animations, themes)
├── services/
│   ├── abstractive.py    # Google Gemini abstractive summary generator
│   ├── cleaner.py        # Text clean, spacy tokenization & sentence split
│   ├── embeddings.py     # Sentence boundary chunker & sentence-transformers
│   ├── extractive.py     # Sumy TextRank extractive summary
│   ├── metadata.py       # spaCy NER and Gemini structured insights generator
│   ├── rag.py            # FAISS index builder, loader, and query search
│   └── scraper.py        # Web scraper (Trafilatura, Newspaper3k, BS4)
├── utils/
│   ├── db.json           # Initial JSON placeholder
│   ├── db.py             # JSON DB file managers
│   └── export.py         # PDF (FPDF2), Markdown, TXT, JSON compiler
├── vectorstore/          # Article-specific FAISS index folders
├── .env.example          # Template environment config
├── requirements.txt      # Python dependencies
└── README.md             # Guide documentation
```

---

## Setup & Installation

### 1. Prerequisite
Ensure you have Python 3.9+ installed on your system.

### 2. Clone/Move to Workspace
Navigate to the directory of the project:
```bash
cd C:\Users\Neha\.gemini\antigravity\scratch\AI-Article-Summarizer
```

### 3. Create Virtual Environment
Create and activate a virtual environment:
```powershell
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 4. Install Dependencies
Install all NLP, ML, and server dependencies:
```bash
pip install -r requirements.txt
```
> **Note**: On the first run, `cleaner.py` will automatically download the spaCy `en_core_web_sm` model, and `extractive.py` will download NLTK tokenizers (`punkt`, `stopwords`) automatically.

### 5. Setup Environment File
Copy the example environment configuration:
```bash
copy .env.example .env
```
Open the `.env` file and fill in your **Google Gemini API Key**:
```env
GEMINI_API_KEY=AIzaSy...
```

---

## Running the Application

Start the Uvicorn dev server:
```bash
uvicorn backend.main:app --reload --port 8000
```

Open your browser and navigate to:
```
http://localhost:8000
```
*(The FastAPI backend automatically serves the frontend interface static assets at the root URL).*

---

## Chat Slash Commands

When an article is loaded, you can type the following commands directly in the chat box to fetch pre-compiled modules:

- `/summary` or `/abstractive` - Prints the abstractive summary
- `/extractive` - Prints the 5–10 key sentences extracted from the text
- `/keywords` - Lists the top terms in the article
- `/entities` - Displays extracted named entities (People, Organizations, etc.)
- `/mcq` - Reprints the comprehension quiz questions
- `/flashcards` - Lists the interactive study flashcards
- `/sentiment` - Shows sentiment and topic categorization
- `/timeline` - Displays the extracted chronological timeline of events
- `/export` - Provides information on how to export reports
