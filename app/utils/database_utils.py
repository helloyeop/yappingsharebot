from sqlalchemy.orm import Session
from app.models.models import User, Tweet, Tag, tweet_tags
from app.schemas.schemas import UserCreate
from typing import Optional

def get_or_create_user(db: Session, telegram_id: int, telegram_username: str, display_name: str) -> User:
    """
    텔레그램 사용자를 데이터베이스에서 찾거나 새로 생성합니다.
    
    Args:
        db: 데이터베이스 세션
        telegram_id: 텔레그램 사용자 ID
        telegram_username: 텔레그램 사용자명
        display_name: 표시할 이름
    
    Returns:
        User: 사용자 객체
    """
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    
    if user:
        if user.telegram_username != telegram_username or user.display_name != display_name:
            user.telegram_username = telegram_username
            user.display_name = display_name
            db.commit()
            db.refresh(user)
        return user
    
    new_user = User(
        telegram_id=telegram_id,
        telegram_username=telegram_username,
        display_name=display_name
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def get_or_create_tag(db: Session, tag_name: str) -> Tag:
    """
    태그를 데이터베이스에서 찾거나 새로 생성합니다.
    
    Args:
        db: 데이터베이스 세션
        tag_name: 태그 이름
    
    Returns:
        Tag: 태그 객체
    """
    tag = db.query(Tag).filter(Tag.name == tag_name.lower()).first()
    
    if tag:
        return tag
    
    new_tag = Tag(name=tag_name.lower())
    db.add(new_tag)
    db.commit()
    db.refresh(new_tag)
    return new_tag