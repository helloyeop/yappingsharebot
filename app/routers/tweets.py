from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func
from app.db.database import get_db
from app.models.models import Tweet, User, Tag, tweet_tags
from app.schemas.schemas import TweetCreate, Tweet as TweetSchema, TweetResponse
from app.utils.database_utils import get_or_create_user, get_or_create_tag
from app.utils.twitter_utils import extract_tweet_id_from_url, validate_twitter_url, normalize_twitter_url
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta

router = APIRouter()

@router.post("/tweets", response_model=TweetSchema)
def create_tweet(tweet: TweetCreate, db: Session = Depends(get_db)):
    """
    새로운 트윗을 등록합니다.
    
    Args:
        tweet: 트윗 생성 데이터 (TweetCreate 스키마)
        db: 데이터베이스 세션
    
    Returns:
        Tweet: 생성된 트윗 정보
    
    Raises:
        HTTPException: 유효하지 않은 URL이나 중복 트윗일 경우
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Creating tweet for user_id: {tweet.user_id}, URL: {tweet.tweet_url}")
    logger.info(f"Tweet data: {tweet.dict()}")
    # 1. 트위터 URL 유효성 검증
    if not validate_twitter_url(tweet.tweet_url):
        raise HTTPException(
            status_code=400, 
            detail="유효하지 않은 트위터 URL입니다."
        )
    
    # 2. 트윗 ID 추출
    tweet_id = extract_tweet_id_from_url(tweet.tweet_url)
    if not tweet_id:
        raise HTTPException(
            status_code=400,
            detail="트위터 URL에서 트윗 ID를 추출할 수 없습니다."
        )
    
    # 3. 중복 트윗 체크
    existing_tweet = db.query(Tweet).filter(Tweet.tweet_id == tweet_id).first()
    if existing_tweet:
        raise HTTPException(
            status_code=400,
            detail="이미 등록된 트윗입니다."
        )
    
    # 4. URL 정규화
    normalized_url = normalize_twitter_url(tweet.tweet_url)
    
    # 5. 사용자 정보 확인 (실제로는 텔레그램에서 사용자 정보를 받아야 함)
    # 여기서는 임시로 user_id로 사용자를 찾습니다
    user = db.query(User).filter(User.telegram_id == tweet.user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다. 먼저 봇을 통해 등록해주세요."
        )
    
    # 6. 새 트윗 생성
    new_tweet = Tweet(
        user_id=tweet.user_id,
        tweet_url=normalized_url,
        tweet_id=tweet_id,
        comment=tweet.comment,
        content_preview="",  # 나중에 Twitter API로 가져올 예정
        image_url=""  # 나중에 Twitter API로 가져올 예정
    )
    
    # 7. 태그 처리
    if tweet.tags:
        for tag_name in tweet.tags:
            if tag_name.strip():  # 빈 태그 제외
                tag = get_or_create_tag(db, tag_name.strip())
                new_tweet.tags.append(tag)
    
    # 8. 데이터베이스에 저장
    db.add(new_tweet)
    db.commit()
    db.refresh(new_tweet)
    
    return new_tweet

@router.get("/tweets", response_model=TweetResponse)
def get_tweets(
    skip: int = Query(0, ge=0, description="건너뛸 트윗 수"),
    limit: int = Query(20, ge=1, le=100, description="한 페이지당 트윗 수"),
    user_id: Optional[int] = Query(None, description="특정 사용자의 트윗만 조회"),
    username: Optional[str] = Query(None, description="사용자명으로 필터링"),
    tag: Optional[str] = Query(None, description="특정 태그의 트윗만 조회"),
    tags: Optional[List[str]] = Query(None, description="여러 태그로 필터링 (OR 조건)"),
    search: Optional[str] = Query(None, description="트윗 내용 검색"),
    date_from: Optional[datetime] = Query(None, description="시작 날짜 (YYYY-MM-DD)"),
    date_to: Optional[datetime] = Query(None, description="종료 날짜 (YYYY-MM-DD)"),
    sort_by: Optional[str] = Query("newest", description="정렬 기준: newest, oldest"),
    db: Session = Depends(get_db)
):
    """
    트윗 목록을 조회합니다. 다양한 필터링과 정렬 옵션을 제공합니다.
    
    필터링 예시:
    - /api/tweets?user_id=12345 - 특정 사용자의 트윗
    - /api/tweets?tag=crypto - crypto 태그가 있는 트윗
    - /api/tweets?tags=crypto&tags=bitcoin - crypto 또는 bitcoin 태그
    - /api/tweets?search=좋은정보 - 코멘트에 "좋은정보" 포함
    - /api/tweets?date_from=2024-01-01&date_to=2024-01-31 - 특정 기간
    """
    # 기본 쿼리 - eager loading으로 N+1 문제 방지
    query = db.query(Tweet)\
        .options(joinedload(Tweet.user))\
        .options(joinedload(Tweet.tags))
    
    # 사용자 필터
    if user_id:
        query = query.filter(Tweet.user_id == user_id)
    elif username:
        query = query.join(User).filter(User.telegram_username.ilike(f"%{username}%"))
    
    # 태그 필터
    if tags and len(tags) > 0:
        # 여러 태그 중 하나라도 있으면 (OR 조건)
        tag_filters = []
        for tag_name in tags:
            tag_filters.append(Tag.name.ilike(f"%{tag_name.lower()}%"))
        query = query.join(Tweet.tags).filter(or_(*tag_filters))
    elif tag:
        # 단일 태그 필터
        query = query.join(Tweet.tags).filter(Tag.name.ilike(f"%{tag.lower()}%"))
    
    # 검색 필터
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Tweet.comment.ilike(search_term),
                Tweet.content_preview.ilike(search_term),
                Tweet.tweet_url.ilike(search_term)
            )
        )
    
    # 날짜 필터
    if date_from:
        query = query.filter(Tweet.created_at >= date_from)
    if date_to:
        # 종료일의 23:59:59까지 포함
        date_to_end = date_to + timedelta(days=1) - timedelta(seconds=1)
        query = query.filter(Tweet.created_at <= date_to_end)
    
    # 중복 제거 (태그 조인 시 필요)
    if tag or tags:
        query = query.distinct()
    
    # 전체 개수 계산
    total = query.count()
    
    # 정렬
    if sort_by == "oldest":
        query = query.order_by(Tweet.created_at.asc())
    else:  # newest (기본값)
        query = query.order_by(Tweet.created_at.desc())
    
    # 페이징 적용
    tweets = query.offset(skip).limit(limit).all()
    
    # 현재 페이지 계산
    current_page = (skip // limit) + 1 if limit > 0 else 1
    
    return TweetResponse(
        tweets=tweets,
        total=total,
        page=current_page,
        size=limit
    )

@router.get("/tweets/{tweet_id}", response_model=TweetSchema)
def get_tweet(tweet_id: UUID, db: Session = Depends(get_db)):
    """
    특정 트윗의 상세 정보를 조회합니다.
    
    Args:
        tweet_id: 조회할 트윗의 UUID
        db: 데이터베이스 세션
    
    Returns:
        Tweet: 트윗 상세 정보
    
    Raises:
        HTTPException: 트윗을 찾을 수 없는 경우
    """
    tweet = db.query(Tweet).filter(Tweet.id == tweet_id).first()
    
    if not tweet:
        raise HTTPException(
            status_code=404,
            detail="트윗을 찾을 수 없습니다."
        )
    
    return tweet

@router.delete("/tweets/{tweet_id}")
def delete_tweet(
    tweet_id: UUID,
    user_id: int = Query(..., description="삭제를 요청하는 사용자 ID"),
    db: Session = Depends(get_db)
):
    """
    트윗을 삭제합니다. 본인이 작성한 트윗만 삭제할 수 있습니다.
    
    Args:
        tweet_id: 삭제할 트윗의 UUID
        user_id: 삭제를 요청하는 사용자의 텔레그램 ID
        db: 데이터베이스 세션
    
    Returns:
        dict: 삭제 성공 메시지
    
    Raises:
        HTTPException: 트윗을 찾을 수 없거나 삭제 권한이 없는 경우
    """
    # 트윗 조회
    tweet = db.query(Tweet).filter(Tweet.id == tweet_id).first()
    
    if not tweet:
        raise HTTPException(
            status_code=404,
            detail="트윗을 찾을 수 없습니다."
        )
    
    # 권한 확인 (본인이 작성한 트윗만 삭제 가능)
    if tweet.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="본인이 작성한 트윗만 삭제할 수 있습니다."
        )
    
    # 트윗 삭제
    db.delete(tweet)
    db.commit()
    
    return {"message": "트윗이 성공적으로 삭제되었습니다."}