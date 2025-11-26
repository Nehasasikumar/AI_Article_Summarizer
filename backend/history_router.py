from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session, joinedload

import models
import auth
import database
import models_db

router = APIRouter()

@router.get("/history", response_model=models.HistoryResponse)
async def history(email: str = Depends(auth.get_email_from_token), db: Session = Depends(database.get_db)):
    # Get user
    db_user = db.query(models_db.User).filter(models_db.User.email == email).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Retrieve all chats for the user, sorted by timestamp descending, with messages
    chats_db = db.query(models_db.Chat).options(joinedload(models_db.Chat.messages)).filter(
        models_db.Chat.user_id == db_user.id
    ).order_by(models_db.Chat.timestamp.desc()).all()

    print(f"DEBUG: Found {len(chats_db)} chats in database for {email}")

    # Convert to response format
    chats = []
    for chat in chats_db:
        chat_dict = {
            "id": chat.chat_id,
            "title": chat.title,
            "timestamp": chat.timestamp.isoformat(),
            "messages": [
                {
                    "id": f"{msg.type}_{msg.timestamp.timestamp()}",  # Match original format
                    "type": msg.type,
                    "content": msg.content,
                    "url": msg.url,
                    "timestamp": msg.timestamp.isoformat()
                }
                for msg in chat.messages
            ]
        }
        chats.append(chat_dict)

    return models.HistoryResponse(chats=chats)

@router.delete("/summary/{chat_id}")
async def delete_summary(
    chat_id: str,
    email: str = Depends(auth.get_email_from_token),
    db: Session = Depends(database.get_db)
):
    # Get user
    db_user = db.query(models_db.User).filter(models_db.User.email == email).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Find and delete chat
    chat_to_delete = db.query(models_db.Chat).filter(
        models_db.Chat.user_id == db_user.id,
        models_db.Chat.chat_id == chat_id
    ).first()

    if not chat_to_delete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Summary not found"
        )

    db.delete(chat_to_delete)
    db.commit()

    return {"message": "Summary deleted"}

@router.put("/summary/{chat_id}")
async def rename_summary(
    chat_id: str,
    request: models.RenameRequest,
    email: str = Depends(auth.get_email_from_token),
    db: Session = Depends(database.get_db)
):
    # Get user
    db_user = db.query(models_db.User).filter(models_db.User.email == email).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    new_title = request.title

    # Update title
    result = db.query(models_db.Chat).filter(
        models_db.Chat.user_id == db_user.id,
        models_db.Chat.chat_id == chat_id
    ).update({"title": new_title})

    if result == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Summary not found"
        )

    db.commit()

    return {"message": "Title updated"}
