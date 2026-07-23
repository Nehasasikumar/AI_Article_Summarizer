import uvicorn
from dotenv import load_dotenv

if __name__ == "__main__":
    # Load environment variables from .env
    load_dotenv()
    
    print("Starting AURA Server...")
    print("Open http://localhost:8000 in your browser.")
    
    # Run the uvicorn server pointing to main.py's app instance
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
