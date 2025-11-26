from datetime import datetime
import traceback
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

import models
import auth
import agent
import database
import models_db

router = APIRouter()

summarize_agent = agent.SummarizeAgent()

@router.post("/summarize", response_model=models.SummarizeResponse)
async def summarize(
    request: models.SummarizeRequest,
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

    url = request.url
    chat_id = request.chat_id

    try:
        summary_text, article_title = summarize_agent.process(url)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Summarization failed: {str(e)}"
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Summarization failed: {str(e)}"
        )

    # Handle chat creation and message storage
    current_time = datetime.utcnow()

    if not chat_id:
        # Create new chat
        chat_id = str(current_time.timestamp())
        new_chat = models_db.Chat(
            user_id=db_user.id,
            chat_id=chat_id,
            title=article_title,
            timestamp=current_time
        )
        db.add(new_chat)
        db.commit()
        db.refresh(new_chat)

        # Add messages
        user_message = models_db.Message(
            chat_id=new_chat.id,
            type='user',
            content=url,
            url=url,
            timestamp=current_time
        )
        assistant_message = models_db.Message(
            chat_id=new_chat.id,
            type='assistant',
            content=summary_text,
            timestamp=current_time
        )
        db.add(user_message)
        db.add(assistant_message)
        db.commit()
    else:
        # Update existing chat with new messages
        existing_chat = db.query(models_db.Chat).filter(
            models_db.Chat.user_id == db_user.id,
            models_db.Chat.chat_id == chat_id
        ).first()
        if existing_chat:
            user_message = models_db.Message(
                chat_id=existing_chat.id,
                type='user',
                content=url,
                url=url,
                timestamp=current_time
            )
            assistant_message = models_db.Message(
                chat_id=existing_chat.id,
                type='assistant',
                content=summary_text,
                timestamp=current_time
            )
            db.add(user_message)
            db.add(assistant_message)
            existing_chat.timestamp = current_time
            db.commit()
        else:
            # If chat_id provided but not exists, create new
            new_chat = models_db.Chat(
                user_id=db_user.id,
                chat_id=chat_id,
                title=article_title,
                timestamp=current_time
            )
            db.add(new_chat)
            db.commit()
            db.refresh(new_chat)

            user_message = models_db.Message(
                chat_id=new_chat.id,
                type='user',
                content=url,
                url=url,
                timestamp=current_time
            )
            assistant_message = models_db.Message(
                chat_id=new_chat.id,
                type='assistant',
                content=summary_text,
                timestamp=current_time
            )
            db.add(user_message)
            db.add(assistant_message)
            db.commit()

    return models.SummarizeResponse(
        summary=summary_text,
        title=article_title,
        chat_id=chat_id
    )
