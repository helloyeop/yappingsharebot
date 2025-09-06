from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.database import get_db
from app.models.models import Tweet, User, Tag
from app.schemas.schemas import StatsResponse
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    """
    전체 통계 정보를 조회합니다.
    
    Args:
        db: 데이터베이스 세션
    
    Returns:
        StatsResponse: 전체 통계 정보
    """
    # 전체 트윗 수
    total_tweets = db.query(Tweet).count()
    
    # 전체 사용자 수
    total_users = db.query(User).count()
    
    # 전체 태그 수
    total_tags = db.query(Tag).count()
    
    # 오늘 등록된 트윗 수
    today = datetime.now().date()
    tweets_today = db.query(Tweet)\
        .filter(func.date(Tweet.created_at) == today)\
        .count()
    
    # 가장 활발한 사용자 (가장 많은 트윗을 공유한 사용자)
    most_active_user_query = db.query(
        User.telegram_username,
        func.count(Tweet.id).label('tweet_count')
    ).join(Tweet)\
    .group_by(User.telegram_id, User.telegram_username)\
    .order_by(func.count(Tweet.id).desc())\
    .first()
    
    most_active_user = most_active_user_query[0] if most_active_user_query else None
    
    return StatsResponse(
        total_tweets=total_tweets,
        total_users=total_users,
        total_tags=total_tags,
        tweets_today=tweets_today,
        most_active_user=most_active_user
    )