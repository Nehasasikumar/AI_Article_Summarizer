import os
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import services
from backend.services import (
    scrape_article,
    get_extractive_summary,
    get_abstractive_summary,
    build_vectorstore,
    query_rag,
    delete_vectorstore
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="AURA - AI Summarizer & Brainstormer")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths configuration
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(PROJECT_ROOT, "database")
DB_FILE = os.path.join(DB_DIR, "db.json")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

# ==============================================================================
# DATABASE MANAGEMENT (Simple JSON File)
# ==============================================================================

def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    if not os.path.exists(DB_FILE):
        import json
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)

def get_db_articles() -> Dict[str, Any]:
    init_db()
    try:
        import json
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading database: {e}")
        return {}

def save_db_article(article_id: str, data: Dict[str, Any]):
    init_db()
    try:
        import json
        articles = get_db_articles()
        articles[article_id] = data
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving to database: {e}")

def delete_db_article(article_id: str) -> bool:
    init_db()
    try:
        import json
        articles = get_db_articles()
        if article_id in articles:
            del articles[article_id]
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(articles, f, ensure_ascii=False, indent=2)
            return True
    except Exception as e:
        logger.error(f"Error deleting from database: {e}")
    return False

# ==============================================================================
# REQUEST & RESPONSE MODELS
# ==============================================================================

class AnalyzeRequest(BaseModel):
    url: str

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    article_id: str
    question: str
    chat_history: List[ChatMessage] = []

# ==============================================================================
# API ROUTING ENDPOINTS
# ==============================================================================

@app.get("/api/history")
async def get_history():
    """Returns a list of previously analyzed articles with their metadata."""
    articles = get_db_articles()
    history = []
    for art_id, data in articles.items():
        history.append({
            "id": art_id,
            "title": data.get("title", "Untitled"),
            "author": data.get("author", "Unknown"),
            "source_url": data.get("source_url", ""),
            "timestamp": data.get("timestamp", "")
        })
    # Return newest first
    history.reverse()
    return history

@app.post("/api/analyze")
async def analyze_url(request: AnalyzeRequest):
    """Scrapes the URL, generates extractive/abstractive summaries, and saves FAISS RAG index."""
    url = request.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL cannot be empty.")
    
    try:
        logger.info(f"Analyzing webpage: {url}")
        
        # Step 1: Scrape text
        article_data = scrape_article(url)
        
        # Step 2: Extractive TextRank Summary
        logger.info("Generating extractive TextRank summary...")
        extractive = get_extractive_summary(article_data["content"], sentence_count=5)
        
        # Step 3: Abstractive Gemini Summary
        logger.info("Generating abstractive Gemini summary...")
        abstractive = get_abstractive_summary(article_data["title"], article_data["content"])
        
        # Step 4: Generate RAG Vector Store (FAISS index)
        logger.info("Building FAISS index...")
        article_id = str(uuid.uuid4())
        build_vectorstore(article_id, article_data["content"])
        
        # Save complete object to DB
        full_data = {
            "id": article_id,
            "title": article_data["title"],
            "author": article_data["author"],
            "date": article_data["date"],
            "content": article_data["content"],
            "source_url": article_data["source_url"],
            "extractive_summary": extractive,
            "abstractive_summary": abstractive,
            "timestamp": datetime.utcnow().isoformat()
        }
        save_db_article(article_id, full_data)
        logger.info(f"Analysis completed successfully: {article_id}")
        return full_data
        
    except ValueError as val_err:
        logger.error(f"Validation/Extraction error: {val_err}")
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as e:
        logger.error(f"Server error during analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/api/chat")
async def chat_with_article(request: ChatRequest):
    """Answers user's question grounded in the retrieved FAISS vector chunks of the article."""
    articles = get_db_articles()
    if request.article_id not in articles:
        raise HTTPException(status_code=404, detail="Article ID not found in database.")
    
    try:
        history = [{"role": msg.role, "content": msg.content} for msg in request.chat_history]
        response = query_rag(request.article_id, request.question, history)
        return {"response": response}
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/article/{article_id}")
async def get_article(article_id: str):
    """Retrieves full analysis details for a single article by its ID."""
    articles = get_db_articles()
    if article_id not in articles:
        raise HTTPException(status_code=404, detail="Article not found.")
    return articles[article_id]

@app.delete("/api/article/{article_id}")
async def delete_article(article_id: str):
    """Deletes an article from the database and removes its FAISS vectorstore index."""
    if delete_db_article(article_id):
        delete_vectorstore(article_id)
        return {"status": "success", "message": "Article deleted."}
    raise HTTPException(status_code=404, detail="Article not found.")

@app.get("/api/export/{article_id}")
async def export_article(article_id: str):
    """Generates a downloadable Markdown report for the analyzed article."""
    articles = get_db_articles()
    if article_id not in articles:
        raise HTTPException(status_code=404, detail="Article not found.")
    
    art = articles[article_id]
    ext_sum_text = "\n".join([f"- {s}" for s in art.get("extractive_summary", [])])
    
    report_content = f"""# AURA Report: {art.get('title')}

**Author:** {art.get('author', 'Unknown')}
**Date:** {art.get('date', 'Unknown')}
**Source:** {art.get('source_url', 'N/A')}
**Timestamp:** {art.get('timestamp', '')}

---

## Abstractive Summary
{art.get('abstractive_summary', '')}

---

## Key Sentences (Extractive)
{ext_sum_text}
"""
    return PlainTextResponse(
        content=report_content,
        headers={"Content-Disposition": f"attachment; filename=aura_report_{article_id}.md"}
    )

# ==============================================================================
# STATIC FILES SERVING (SPA)
# ==============================================================================

@app.get("/")
async def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return PlainTextResponse("Frontend index.html not found.")

# Serve other static files (css, js)
app.mount("/", StaticFiles(directory=FRONTEND_DIR), name="static")
