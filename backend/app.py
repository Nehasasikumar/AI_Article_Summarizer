from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS, cross_origin
from pymongo import MongoClient
import bcrypt
import jwt
from datetime import datetime, timedelta
from newspaper import Article
from transformers import pipeline
import spacy
import traceback
import re
from urllib.parse import unquote
import requests
from bs4 import BeautifulSoup
import os

# Load spaCy and BART models
nlp = spacy.load("en_core_web_sm")
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

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

# ----------------- EXTRACTIVE SUMMARY (spaCy) -----------------
def extractive_summary_spacy(text, sentence_count=7):
    doc = nlp(text)
    sentences = list(doc.sents)

    ranked = sorted(sentences, key=lambda s: sum(1 for token in s if token.pos_ in ['NOUN', 'PROPN']), reverse=True)
    top_sentences = sorted(ranked[:sentence_count], key=lambda s: s.start)
    return " ".join(str(s).strip() for s in top_sentences)

# ----------------- SUMMARIZE -----------------
@app.route('/api/summarize', methods=['POST'])
def summarize():
    email, error = get_email_from_token(request.headers.get('Authorization'))
    if error:
        return jsonify({'error': error}), 401

    data = request.get_json()
    url = data.get('url')
    chat_id = data.get('chat_id')
    messages = data.get('messages')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        article_title = soup.title.string if soup.title else "Untitled"

        paragraphs = soup.find_all('p')
        article_text = ' '.join([p.get_text() for p in paragraphs])

        if not article_text.strip():
            raise ValueError("Article content is empty")

        # Step 1: Summarize each chunk
        chunks = [article_text[i:i+1024] for i in range(0, len(article_text), 1024)]
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            print(f"Summarizing chunk {i+1}/{len(chunks)}")
            output = summarizer(chunk, max_length=150, min_length=40, do_sample=False)
            chunk_summaries.append(output[0]['summary_text'])
        
        # Step 2: Combine chunk summaries and create a final summary
        combined_summary = " ".join(chunk_summaries)

        # If the combined summary is short, no need for another summarization pass.
        if len(combined_summary.split()) < 150:
            summary_text = combined_summary
        else:
            print("Creating final summary...")
            final_summary_output = summarizer(combined_summary, max_length=512, min_length=100, do_sample=False)
            summary_text = final_summary_output[0]['summary_text']

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Summarization failed: {str(e)}'}), 500

    if chat_id:
        history_collection.update_one(
            {'email': email, 'id': chat_id},
            {'$set': {'messages': messages, 'timestamp': datetime.now().isoformat(), 'title': article_title}},
            upsert=True
        )
    else:
        chat_id = str(datetime.now().timestamp())
        history_collection.insert_one({
            "id": chat_id,
            "email": email,
            "title": article_title,
            "messages": messages,
            "timestamp": datetime.now().isoformat()
        })


    return jsonify({
        "summary": summary_text,
        "title": article_title,
        "chat_id": chat_id
    }), 200

# ----------------- HISTORY -----------------
@app.route('/api/history', methods=['GET'])
def history():
    email, error = get_email_from_token(request.headers.get('Authorization'))
    if error:
        return jsonify({'error': error}), 401

    chats = list(history_collection.find({"email": email}, {"_id": 0}))
    return jsonify({"chats": chats}), 200

#from urllib.parse import unquote

# ----------------- DELETE SUMMARY -----------------
@app.route('/api/summary/<id>', methods=['DELETE'])
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

# ----------------- SERVE FRONTEND -----------------
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if path.startswith('api/'):
        return jsonify({'error': 'API route not found'}), 404
    if os.path.exists(f'frontend/dist/{path}') and os.path.isfile(f'frontend/dist/{path}'):
        return send_from_directory('frontend/dist', path)
    else:
        return send_from_directory('frontend/dist', 'index.html')

# ----------------- MAIN -----------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Server running at http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
