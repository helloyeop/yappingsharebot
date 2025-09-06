from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import User, Tweet
from app.schemas.schemas import UserCreate, User as UserSchema
from app.utils.database_utils import get_or_create_user
from typing import List, Optional

router = APIRouter()

@router.post("/users", response_model=UserSchema)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    사용자를 생성하거나 업데이트합니다.
    
    Args:
        user: 사용자 생성 데이터
        db: 데이터베이스 세션
    
    Returns:
        User: 생성되거나 업데이트된 사용자 정보
    """
    created_user = get_or_create_user(
        db=db,
        telegram_id=user.telegram_id,
        telegram_username=user.telegram_username,
        display_name=user.display_name
    )
    return created_user

@router.get("/users", response_model=List[UserSchema])
def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None, description="사용자명 검색"),
    sort_by: Optional[str] = Query("active", description="정렬: active, newest, alphabetical"),
    db: Session = Depends(get_db)
):
    """
    사용자 목록을 조회합니다.
    
    Args:
        skip: 건너뛸 사용자 수
        limit: 조회할 사용자 수
        search: 사용자명 검색어
        sort_by: 정렬 기준 (active: 활동순, newest: 최신순, alphabetical: 알파벳순)
        db: 데이터베이스 세션
    
    Returns:
        List[User]: 사용자 목록
    """
    from sqlalchemy import func
    
    # 기본 쿼리
    query = db.query(User)
    
    # 검색 필터
    if search:
        query = query.filter(
            User.telegram_username.ilike(f"%{search}%") |
            User.display_name.ilike(f"%{search}%")
        )
    
    # 활성 사용자만 필터링
    query = query.filter(User.is_active == True)
    
    # 정렬
    if sort_by == "active":
        # 활동순 (트윗 수가 많은 순) - 서브쿼리 사용
        tweet_count_subquery = db.query(
            Tweet.user_id,
            func.count(Tweet.id).label('tweet_count')
        ).group_by(Tweet.user_id).subquery()
        
        query = query.outerjoin(
            tweet_count_subquery,
            User.telegram_id == tweet_count_subquery.c.user_id
        ).order_by(
            func.coalesce(tweet_count_subquery.c.tweet_count, 0).desc()
        )
    elif sort_by == "newest":
        # 최신 가입순
        query = query.order_by(User.created_at.desc())
    else:  # alphabetical
        # 알파벳순
        query = query.order_by(User.telegram_username.asc())
    
    # 페이징 적용
    users = query.offset(skip).limit(limit).all()
    
    return users

@router.get("/users/{user_id}", response_model=UserSchema)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """
    특정 사용자의 정보를 조회합니다.
    
    Args:
        user_id: 사용자의 텔레그램 ID
        db: 데이터베이스 세션
    
    Returns:
        User: 사용자 정보
    
    Raises:
        HTTPException: 사용자를 찾을 수 없는 경우
    """
    user = db.query(User).filter(User.telegram_id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다."
        )
    
    return user

@router.get("/users/stats/top-contributors")
def get_top_contributors(
    days: int = Query(30, description="최근 N일간의 기여자"),
    limit: int = Query(10, ge=1, le=50, description="조회할 사용자 수"),
    db: Session = Depends(get_db)
):
    """
    최근 가장 활발한 기여자 목록을 조회합니다.
    
    Args:
        days: 집계 기간 (일)
        limit: 조회할 사용자 수
        db: 데이터베이스 세션
    
    Returns:
        List[dict]: 상위 기여자 목록
    """
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    # 집계 시작 날짜
    since_date = datetime.now() - timedelta(days=days)
    
    # 최근 N일간 가장 많은 트윗을 공유한 사용자
    top_contributors = db.query(
        User.telegram_id,
        User.telegram_username,
        User.display_name,
        func.count(Tweet.id).label('tweet_count')
    ).join(Tweet)\
    .filter(Tweet.created_at >= since_date)\
    .group_by(User.telegram_id, User.telegram_username, User.display_name)\
    .order_by(func.count(Tweet.id).desc())\
    .limit(limit)\
    .all()
    
    return [
        {
            "user_id": user_id,
            "username": username,
            "display_name": display_name,
            "tweet_count": tweet_count,
            "period_days": days
        }
        for user_id, username, display_name, tweet_count in top_contributors
    ]

@router.get("/users/{user_id}/tweets")
def get_user_tweets(
    user_id: int, 
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    특정 사용자가 공유한 트윗 목록을 조회합니다.
    
    Args:
        user_id: 사용자의 텔레그램 ID
        skip: 건너뛸 트윗 수
        limit: 한 페이지당 트윗 수
        db: 데이터베이스 세션
    
    Returns:
        List[Tweet]: 사용자의 트윗 목록 (최신순)
    
    Raises:
        HTTPException: 사용자를 찾을 수 없는 경우
    """
    # 사용자 존재 확인
    user = db.query(User).filter(User.telegram_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다."
        )
    
    # 사용자의 트윗 조회
    tweets = db.query(Tweet)\
        .filter(Tweet.user_id == user_id)\
        .order_by(Tweet.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    return {
        "user": user,
        "tweets": tweets,
        "total": db.query(Tweet).filter(Tweet.user_id == user_id).count()
    }