import os
import re
import json
import logging
import urllib.parse
from typing import List, Dict, Any, Optional

import requests
import numpy as np
import trafilatura
from bs4 import BeautifulSoup
from newspaper import Article as NewspaperArticle

# Sumy components
import nltk
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer

# Gemini & ML imports
import google.generativeai as genai
import faiss
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. SCRAPING, CLEANING & SENTENCE SEGMENTATION SERVICES
# ==============================================================================

def validate_url(url: str) -> bool:
    """Checks if the string is a valid URL with scheme and network location."""
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def scrape_article(url: str) -> Dict[str, Any]:
    """
    Downloads and extracts article components: Title, Author, Date, Text Body.
    Uses Trafilatura as primary scraper, falling back to Newspaper3k and BeautifulSoup.
    """
    if not validate_url(url):
        raise ValueError(f"Invalid URL structure: '{url}'")

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/115.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }

    html_content = ""
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        html_content = response.text
    except Exception as e:
        logger.error(f"Failed download via requests: {e}")
        try:
            html_content = trafilatura.fetch_url(url)
        except Exception as t_err:
            logger.error(f"Failed download via Trafilatura: {t_err}")

    if not html_content:
        raise ValueError("Could not retrieve webpage content. The site may be blocking requests.")

    title, author, date, content = None, None, None, None

    # Step 1: Trafilatura Extraction
    try:
        extracted = trafilatura.extract(html_content, output_format='json', include_comments=False)
        if extracted:
            data = json.loads(extracted)
            title = data.get('title')
            author = data.get('author')
            date = data.get('date')
            content = data.get('text')
    except Exception as e:
        logger.warning(f"Trafilatura failed: {e}")

    # Step 2: Newspaper3k Fallback
    if not content or not title:
        try:
            article = NewspaperArticle(url)
            article.set_html(html_content)
            article.parse()
            title = title or article.title
            author = author or (article.authors[0] if article.authors else None)
            date = date or (article.publish_date.isoformat() if article.publish_date else None)
            content = content or article.text
        except Exception as ne:
            logger.warning(f"Newspaper3k fallback failed: {ne}")

    # Step 3: BeautifulSoup Fallback
    if not content:
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            for tag in soup(["script", "style", "nav", "footer", "aside", "header", "head", "iframe", "noscript"]):
                tag.decompose()
            title = title or (soup.title.string if soup.title else None)
            
            # Extract paragraph elements, headings, lists, and table cells for listing pages
            elements = []
            for tag in soup.find_all(['p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'td']):
                txt = tag.get_text().strip()
                if txt and len(txt) > 8:
                    elements.append(txt)
            content = "\n\n".join(elements)
        except Exception as bse:
            logger.error(f"BeautifulSoup fallback failed: {bse}")

    title = title or "Parsed Webpage"
    
    # Final absolute raw text fallback if still empty
    if not content or len(content.strip()) < 10:
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            for tag in soup(["script", "style", "head"]):
                tag.decompose()
            content = soup.get_text()
        except Exception:
            pass

    content = clean_text(content or "")
    if not content or len(content.strip()) < 5:
        raise ValueError("Could not extract any substantial text from the webpage. The site may be blank, blocked, or require login.")

    return {
        "title": title.strip(),
        "author": author.strip() if author else "Unknown",
        "date": date.strip() if date else "Unknown",
        "content": content,
        "source_url": url
    }

def clean_text(text: str) -> str:
    """Removes HTML remnants and normalizes whitespace/paragraphs."""
    cleaned = re.sub(r'<[^>]+>', ' ', text)
    cleaned = cleaned.replace('\xa0', ' ').replace('\u200b', '')
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
    
    # Filter empty lines, group paragraphs
    lines = [line.strip() for line in cleaned.split('\n')]
    paragraphs = []
    current = []
    for line in lines:
        if line:
            current.append(line)
        else:
            if current:
                paragraphs.append(" ".join(current))
                current = []
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs).strip()

def segment_sentences(text: str) -> List[str]:
    """Segments article body text into sentences using simple regex boundaries."""
    if not text:
        return []
    # Splitting on punctuation marks followed by a whitespace character
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|!)\s', text)
    return [s.strip() for s in sentences if s.strip()]

# ==============================================================================
# 2. EXTRACTIVE & ABSTRACTIVE SUMMARIZATION SERVICES
# ==============================================================================

_nltk_downloaded = False

def ensure_nltk_resources():
    """Silently downloads NLTK resources needed for TextRank tokenization."""
    global _nltk_downloaded
    if not _nltk_downloaded:
        for resource in ['punkt', 'stopwords', 'punkt_tab']:
            try:
                if resource in ['punkt', 'punkt_tab']:
                    nltk.data.find(f'tokenizers/{resource}')
                else:
                    nltk.data.find(f'corpora/{resource}')
            except LookupError:
                nltk.download(resource, quiet=True)
        _nltk_downloaded = True

def get_extractive_summary(text: str, sentence_count: int = 5) -> List[str]:
    """Extracts top N key sentences using Sumy's TextRank algorithm."""
    if not text:
        return []
    sentence_count = max(3, min(8, sentence_count))
    try:
        ensure_nltk_resources()
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = TextRankSummarizer()
        summary_sentences = summarizer(parser.document, sentence_count)
        return [str(sent).strip() for sent in summary_sentences if str(sent).strip()]
    except Exception as e:
        logger.error(f"TextRank extractive summarization failed: {e}")
        # Fallback to first few sentences
        sents = segment_sentences(text)
        return sents[:sentence_count]

def get_gemini_model() -> Optional[genai.GenerativeModel]:
    """Initializes and returns the Gemini 3.5 Flash Model."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-3.1-flash-lite')
    except Exception as e:
        logger.error(f"Gemini client setup error: {e}")
        return None

def get_abstractive_summary(title: str, content: str) -> str:
    """Generates a professional 2-3 paragraph abstractive summary using Gemini."""
    model = get_gemini_model()
    if not model:
        raise ValueError("Gemini API key is missing or invalid. Check your .env file.")

    prompt = f"""
You are a professional editor. Write a concise, 2 to 3 paragraph summary of this article.
Do not repeat sentences verbatim. Explaining the article clearly in natural English.

Article Title: {title}
Article Body:
\"\"\"
{content}
\"\"\"

Abstractive Summary:
"""
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.3, max_output_tokens=700),
            request_options={"timeout": 60.0}
        )
        if response.text:
            return response.text.strip()
        raise ValueError("Received empty text response.")
    except Exception as e:
        raise RuntimeError(f"Error calling Gemini: {e}")

# ==============================================================================
# 3. RAG EMBEDDINGS, FAISS VECTOR DATABASE & CHAT SERVICES
# ==============================================================================

# Singletons for lazy loading
_embed_model = None
VECTORSTORE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vectorstore")

def get_embedding_model():
    """Loads SentenceTransformer model for chunk vectorization."""
    global _embed_model
    if _embed_model is None:
        try:
            _embed_model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            raise RuntimeError(f"Failed to load sentence-transformers model: {e}")
    return _embed_model

def chunk_text(text: str, max_words: int = 150, overlap_words: int = 30) -> List[str]:
    """Splits article text into chunks respecting sentence boundaries."""
    sentences = segment_sentences(text)
    chunks = []
    current_chunk = []
    current_words = 0

    for sentence in sentences:
        words = sentence.split()
        len_words = len(words)
        if len_words == 0:
            continue
        
        if current_words + len_words > max_words and current_chunk:
            chunks.append(" ".join(current_chunk))
            # Build overlap from previous sentences
            overlap = []
            overlap_count = 0
            for s in reversed(current_chunk):
                s_words = len(s.split())
                if overlap_count + s_words <= overlap_words:
                    overlap.insert(0, s)
                    overlap_count += s_words
                else:
                    break
            current_chunk = overlap
            current_words = overlap_count

        current_chunk.append(sentence)
        current_words += len_words

    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

def build_vectorstore(article_id: str, content: str) -> None:
    """Chunks the text, calculates embeddings, builds a FAISS index, and saves to folder."""
    chunks = chunk_text(content)
    if not chunks:
        return

    try:
        model = get_embedding_model()
        embeddings = model.encode(chunks, show_progress_bar=False)
        embeddings_np = np.array(embeddings).astype('float32')

        # Create output directory
        target_dir = os.path.join(VECTORSTORE_DIR, article_id)
        os.makedirs(target_dir, exist_ok=True)

        # Build L2 index
        index = faiss.IndexFlatL2(embeddings_np.shape[1])
        index.add(embeddings_np)

        # Save files
        faiss.write_index(index, os.path.join(target_dir, "index.faiss"))
        with open(os.path.join(target_dir, "chunks.json"), 'w', encoding='utf-8') as f:
            json.dump(chunks, f, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error building vectorstore for {article_id}: {e}")

def query_rag(article_id: str, question: str, chat_history: List[Dict[str, str]] = None) -> str:
    """Retrieves relevant article chunks and queries Gemini in a grounded prompt."""
    target_dir = os.path.join(VECTORSTORE_DIR, article_id)
    index_file = os.path.join(target_dir, "index.faiss")
    chunks_file = os.path.join(target_dir, "chunks.json")

    if not os.path.exists(index_file) or not os.path.exists(chunks_file):
        raise FileNotFoundError("RAG Vector workspace files not found for this article.")

    # Step 1: Embedding query
    model = get_embedding_model()
    q_embedding = model.encode([question], show_progress_bar=False)
    q_np = np.array(q_embedding).astype('float32')

    # Step 2: Query FAISS
    index = faiss.read_index(index_file)
    with open(chunks_file, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    
    k = min(4, len(chunks))
    distances, indices = index.search(q_np, k)
    
    context_chunks = []
    for idx in indices[0]:
        if idx != -1 and idx < len(chunks):
            context_chunks.append(chunks[idx])
    
    context = "\n\n".join(context_chunks)

    # Step 3: Call Gemini with context injected prompt
    gemini = get_gemini_model()
    if not gemini:
        raise ValueError("Gemini API key missing or invalid.")

    # Build chat history context
    history_context = ""
    if chat_history:
        for msg in chat_history[-6:]:  # Keep last 3 turns
            role_label = "User" if msg['role'] == 'user' else "AI"
            history_context += f"{role_label}: {msg['content']}\n"

    prompt = f"""
You are AURA, an interactive article brainstorming AI. Your task is to answer the user's question.
You MUST base your answer strictly on the provided context retrieved from the article.
If the answer cannot be found in the context, politely explain that you can only discuss content relative to the article.

Retrieved Article Context:
\"\"\"
{context}
\"\"\"

Conversation History:
{history_context}

User's Question: {question}

AI Response (concise, grounded in the context):
"""
    try:
        response = gemini.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.4, max_output_tokens=600),
            request_options={"timeout": 60.0}
        )
        return response.text.strip() if response.text else "No response generated."
    except Exception as e:
        raise RuntimeError(f"RAG query failed: {e}")

def delete_vectorstore(article_id: str) -> None:
    """Removes stored vector files."""
    target_dir = os.path.join(VECTORSTORE_DIR, article_id)
    if os.path.exists(target_dir):
        import shutil
        shutil.rmtree(target_dir, ignore_errors=True)
