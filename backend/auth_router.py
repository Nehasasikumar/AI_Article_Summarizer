import bcrypt
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

import models
import auth
import database
import models_db

router = APIRouter()

@router.post("/signup", response_model=dict)
async def signup(user: models.UserCreate, db: Session = Depends(database.get_db)):
    # Check if user exists
    existing_user = db.query(models_db.User).filter(models_db.User.email == user.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )

    if not auth.is_strong_password(user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Password must be at least 8 characters long, include uppercase, lowercase, number, and special character.'
        )

    hashed = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    new_user = models_db.User(
        name=user.name,
        email=user.email,
        password=hashed
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "Signup successful"}

@router.post("/login", response_model=models.TokenResponse)
async def login(user: models.UserLogin, db: Session = Depends(database.get_db)):
    db_user = db.query(models_db.User).filter(models_db.User.email == user.email).first()
    if not db_user or not bcrypt.checkpw(user.password.encode('utf-8'), db_user.password.encode('utf-8')):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    token = auth.create_access_token(data={"email": user.email})

    return models.TokenResponse(
        token=token,
        user={"name": db_user.name, "email": db_user.email}
    )
