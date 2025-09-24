# Chatbot – Article Summarizer

## Why is this Needed?

There is a vast amount of information available online, and reading full-length articles can be time-consuming. This project provides a solution by automatically summarizing articles for users. With this tool, anyone can quickly understand the key points of an article by simply pasting its URL. This saves time and helps users focus on relevant information.

## Project Description

This is an AI-powered chatbot web application that allows users to input an article URL and receive an intelligent, concise summary. The chatbot stores the chat history for each summary and enables easy interaction for repeated or new summarizations. It is designed with a modern frontend in TypeScript and React, and a backend using Python, Flask, and machine learning models for natural language processing.

## Features

- **Article Summarization**: Paste any article URL and get a clean, readable summary.
- **Chat-like Interface**: Interact with the summarizer as a conversation.
- **History Storage**: Keeps a record of your past summaries and chats.
- **Authentication**: User sign-up and login for personalized history.
- **Secure**: Uses JWT for secure session management.
- **Modern UI**: Responsive and accessible interface.

## Technologies Used

- **Frontend**: TypeScript, React, Axios
- **Backend**: Python, Flask, Flask-CORS, PyMongo, Newspaper3k, HuggingFace Transformers (T5), spaCy, JWT
- **Database**: MongoDB
- **NLP Models**: T5-large for summarization, spaCy for processing
- **Other**: bcrypt for password hashing

## Getting Started

### Prerequisites

- Node.js (v16 or newer)
- Python 3.8+
- MongoDB running locally (`mongodb://localhost:27017/`)
- [Optional] Virtual environment for Python

### Installation

#### 1. Clone the repository

```bash
git clone https://github.com/Nehasasikumar/chatbot.git
cd chatbot
```

#### 2. Setup the Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
# Make sure MongoDB is running locally
python app.py
```

The backend server will start at [http://localhost:5000](http://localhost:5000).

#### 3. Setup the Frontend

```bash
cd ../frontend
npm install
npm run dev
```

The frontend will be available at [http://localhost:5173](http://localhost:5173) or as specified in the console.

### Usage

1. Sign up and log in to your account.
2. Paste any article URL into the chat input box.
3. The chatbot will fetch, process, and summarize the article.
4. Your past summaries and chats are stored and retrievable.

### Example Workflow

- **Step 1:** Open the web app and sign up.
- **Step 2:** Log in.
- **Step 3:** Paste an article URL (e.g., a news article).
- **Step 4:** Submit to receive a summary.
- **Step 5:** Review and revisit your summaries in history.

## Contribution

Contributions are welcome! Please open an issue to discuss ideas or submit a pull request.


## Acknowledgements

- HuggingFace for T5 summarization model
- spaCy for NLP
- Newspaper3k for article extraction

---
