import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://neondb_owner:npg_xd0oMCYDVhQ2@ep-muddy-tree-a1ae5dws-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require')

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
