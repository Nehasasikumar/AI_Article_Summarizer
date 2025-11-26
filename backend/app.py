from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS, cross_origin
from pymongo import MongoClient
import bcrypt
import jwt
from datetime import datetime, timedelta
import traceback
import re
from urllib.parse import unquote
import requests
from bs4 import BeautifulSoup
import os
import nltk
import heapq

nltk.download('punkt')
nltk.download('stopwords')
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize

# JWT Secret
SECRET_KEY = os.environ.get('SECRET_KEY', 'your_super_secret_key')

# Initialize Flask app
app = Flask(__name__)
CORS(app, origins="*")

# MongoDB Setup
client = MongoClient(os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/'))
db = client['chatbot_db']
users = db['users']
history_collection = db['history']

# ----------------- PASSWORD VALIDATION -----------------
def is_strong_password(password):
    return (
        len(password) >= 8 and
        re.search(r"[A-Z]", password) and
        re.search(r"[a-z]", password) and
        re.search(r"[0-9]", password) and
        re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)
    )

# ----------------- SIGNUP -----------------
@app.route('/api/signup', methods=['POST'])
@cross_origin()
def signup():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if users.find_one({'email': email}):
        return jsonify({'error': 'Email already exists'}), 400

    if not is_strong_password(password):
        return jsonify({
            'error': 'Password must be at least 8 characters long, include uppercase, lowercase, number, and special character.'
        }), 400

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    users.insert_one({'name': name, 'email': email, 'password': hashed})

    return jsonify({'message': 'Signup successful'}), 200

# ----------------- LOGIN -----------------
@app.route('/api/login', methods=['POST'])
@cross_origin()
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = users.find_one({'email': email})
    if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
        return jsonify({'error': 'Invalid credentials'}), 401

    token = jwt.encode(
        {'email': email, 'exp': datetime.utcnow() + timedelta(hours=12)},
        SECRET_KEY,
        algorithm='HS256'
    )

    if isinstance(token, bytes):
        token = token.decode('utf-8')

    return jsonify({
        'token': token,
        'user': {'name': user['name'], 'email': user['email']}
    }), 200

# ----------------- TOKEN VALIDATION -----------------
def get_email_from_token(auth_header):
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, 'Missing or invalid auth header'

    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload.get('email'), None
    except jwt.ExpiredSignatureError:
        return None, 'Token expired'
    except jwt.InvalidTokenError:
        return None, 'Invalid token'

# ----------------- SUMMARIZE -----------------
@app.route('/api/summarize', methods=['POST'])
@cross_origin()
def summarize():
    email = 'anonymous'  # Removed auth requirement

    data = request.get_json()
    url = data.get('url')
    chat_id = data.get('chat_id')
    messages = data.get('messages')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Check if this is a journal homepage vs article page
        is_journal_homepage = url.lower().endswith('?tab=toc') == False and any(indicator in url.lower() for indicator in ['/journal/', '/journals/', 'springer.com/journal'])
        is_article_page = ('/article/' in url.lower() or '/chapter/' in url.lower() or ('/' in url.lower().split('?')[0].split('#')[0] and url.lower().split('?')[0].split('#')[0].count('/') > 3))

        article_title = soup.title.string if soup.title else "Untitled"

        # Check if this is a journal homepage - not suitable for summarization
        if is_journal_homepage and not is_article_page:
            raise ValueError("This appears to be a journal homepage, not a specific article. Please provide a direct link to an article instead of the journal's main page.")

        # Improved content extraction with multiple strategies
        article_text = ""

        # Strategy 1: Try to find main article content containers
        content_selectors = [
            'article',
            '[role="main"]',
            'main',
            '.article-content',
            '.post-content',
            '.entry-content',
            '.content',
            '#content',
            '.article-body',
            '.post-body'
        ]

        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                paragraphs = content_elem.find_all('p')
                article_text = ' '.join([p.get_text() for p in paragraphs])
                if article_text.strip():
                    break

        # Strategy 2: If no content found, try extracting from all paragraphs
        if not article_text.strip():
            paragraphs = soup.find_all('p')
            article_text = ' '.join([p.get_text() for p in paragraphs])

        # Strategy 3: Fallback to extracting text from common content elements
        if not article_text.strip():
            text_elements = soup.find_all(['p', 'div', 'span', 'li'])
            filtered_text = []
            for elem in text_elements:
                text = elem.get_text().strip()
                # Only include text that's meaningful length and not boilerplate
                if len(text) > 20 and not any(skip in text.lower() for skip in ['copyright', 'privacy policy', 'terms of service', 'sign up', 'login', 'subscribe']):
                    filtered_text.append(text)
            article_text = ' '.join(filtered_text)

        # Strategy 4: Last resort - get all body text that's reasonably long
        if not article_text.strip():
            body = soup.find('body')
            if body:
                all_text = body.get_text()
                # Split by double newlines to get paragraph-like chunks
                chunks = [chunk.strip() for chunk in all_text.split('\n\n') if chunk.strip()]
                meaningful_chunks = []
                for chunk in chunks:
                    # Only include chunks that look like content (not navigation/footer)
                    if len(chunk) > 30 and not any(skip in chunk.lower() for skip in [
                        'copyright', 'privacy policy', 'terms of service', 'sign up', 'login', 'subscribe',
                        'cookies', 'accept cookies', 'cookie settings', 'follow us', 'contact us'
                    ]):
                        meaningful_chunks.append(chunk)
                article_text = ' '.join(meaningful_chunks[:20])  # Limit to prevent huge extraction

        if not article_text.strip():
            raise ValueError("Unable to extract article content. The website may not allow automated content extraction.")

        # Extractive summary using NLTK
        stopWords = set(stopwords.words("english"))
        words = word_tokenize(article_text)
        freqTable = dict()
        for word in words:
            word = word.lower()
            if word in stopWords:
                continue
            if word in freqTable:
                freqTable[word] += 1
            else:
                freqTable[word] = 1

        max_freq = max(freqTable.values())
        for word in freqTable:
            freqTable[word] = freqTable[word] / max_freq

        sentences = sent_tokenize(article_text)
        sentenceValue = dict()

        for sentence in sentences:
            for indexed, wordValue in enumerate(word_tokenize(sentence)):
                if wordValue.lower() in freqTable:
                    if sentence in sentenceValue:
                        sentenceValue[sentence] += freqTable[wordValue.lower()]
                    else:
                        sentenceValue[sentence] = freqTable[wordValue.lower()]

        sumValues = 0
        for entry in sentenceValue:
            sumValues += sentenceValue[entry]

        average = int(sumValues / len(sentenceValue))

        summary = heapq.nlargest(7, sentenceValue, key=sentenceValue.get)
        summary_text = ' '.join(summary)

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Summarization failed: {str(e)}'}), 500

    # Skip database operations for demo
    if not chat_id:
        chat_id = str(datetime.now().timestamp())


    return jsonify({
        "summary": summary_text,
        "title": article_title,
        "chat_id": chat_id
    }), 200

# ----------------- HISTORY -----------------
@app.route('/api/history', methods=['GET'])
@cross_origin()
def history():
    email = 'anonymous'  # Removed auth requirement

    # Return empty list since db operations are disabled for demo
    chats = []
    return jsonify({"chats": chats}), 200

# ----------------- DELETE SUMMARY -----------------
@app.route('/api/summary/<id>', methods=['DELETE'])
@cross_origin()
def delete_summary(id):
    email, error = get_email_from_token(request.headers.get('Authorization'))
    if error:
        return jsonify({'error': error}), 401

    result = history_collection.delete_one({'email': email, 'id': id})

    if result.deleted_count == 0:
        return jsonify({'error': 'Summary not found'}), 404

    return jsonify({'message': 'Summary deleted'}), 200

# ----------------- RENAME SUMMARY -----------------
@app.route('/api/summary/<id>', methods=['PUT'])
@cross_origin()
def rename_summary(id):
    email, error = get_email_from_token(request.headers.get('Authorization'))
    if error:
        return jsonify({'error': error}), 401

    data = request.get_json()
    new_title = data.get('title')

    result = history_collection.update_one(
        {'email': email, 'id': id},
        {'$set': {'title': new_title}}
    )

    if result.matched_count == 0:
        return jsonify({'error': 'Summary not found'}), 404

    return jsonify({'message': 'Title updated'}), 200

# ----------------- MAIN -----------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Server running at http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
