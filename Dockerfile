# Use Python 3.10 as base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install Node.js for building frontend
RUN apt-get update && apt-get install -y node.js npm && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy frontend code and build it
COPY frontend/ frontend/
RUN cd frontend && npm install && npm run build

# Expose port
EXPOSE 5000

# Run the app
CMD ["python", "app.py"]
