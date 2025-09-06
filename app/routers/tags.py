from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.db.database import get_db
from app.models.models import Tag, Tweet, tweet_tags
from app.schemas.schemas import TagCreate, Tag as TagSchema
from typing import List, Optional

router = APIRouter()

@router.post("/tags", response_model=TagSchema)
def create_tag(tag_data: dict, db: Session = Depends(get_db)):
    """
    새로운 태그를 생성합니다.
    
    Args:
        tag_data: 태그 생성 데이터 (name, created_by)
        db: 데이터베이스 세션
    
    Returns:
        Tag: 생성된 태그 정보
    
    Raises:
        HTTPException: 태그가 이미 존재하는 경우
    """
    # 태그명 정규화 (소문자 변환)
    tag_name = tag_data.get("name", "").lower().strip()
    created_by = tag_data.get("created_by")
    
    if not tag_name:
        raise HTTPException(status_code=400, detail="태그명을 입력해주세요.")
    
    # 중복 확인
    existing_tag = db.query(Tag).filter(Tag.name == tag_name).first()
    if existing_tag:
        # 비활성화된 태그면 다시 활성화
        if not existing_tag.is_active:
            existing_tag.is_active = True
            db.commit()
            db.refresh(existing_tag)
            return existing_tag
        else:
            raise HTTPException(
                status_code=400,
                detail=f"태그 '{tag_name}'이(가) 이미 존재합니다."
            )
    
    # 새 태그 생성
    new_tag = Tag(
        name=tag_name,
        created_by=created_by,
        is_core=False  # 사용자가 추가한 태그
    )
    db.add(new_tag)
    db.commit()
    db.refresh(new_tag)
    
    return new_tag

@router.get("/tags", response_model=List[TagSchema])
def get_tags(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None, description="태그명 검색"),
    sort_by: Optional[str] = Query("popular", description="정렬: popular, newest, alphabetical"),
    db: Session = Depends(get_db)
):
    """
    태그 목록을 조회합니다.
    
    Args:
        skip: 건너뛸 태그 수
        limit: 조회할 태그 수
        search: 태그명 검색어
        sort_by: 정렬 기준 (popular: 사용 빈도순, newest: 최신순, alphabetical: 알파벳순)
        db: 데이터베이스 세션
    
    Returns:
        List[Tag]: 태그 목록
    """
    # 기본 쿼리 - 트윗 개수와 함께 조회 (활성 태그만)
    query = db.query(
        Tag,
        func.count(tweet_tags.c.tweet_id).label('tweet_count')
    ).filter(Tag.is_active == True)\
    .outerjoin(tweet_tags)\
    .group_by(Tag.id)
    
    # 검색 필터
    if search:
        query = query.filter(Tag.name.ilike(f"%{search}%"))
    
    # 정렬
    if sort_by == "popular":
        # 사용 빈도순 (트윗 개수가 많은 순)
        query = query.order_by(desc('tweet_count'))
    elif sort_by == "newest":
        # 최신순
        query = query.order_by(Tag.created_at.desc())
    else:  # alphabetical
        # 알파벳순
        query = query.order_by(Tag.name.asc())
    
    # 페이징 적용
    results = query.offset(skip).limit(limit).all()
    
    # 태그 객체에 tweet_count 업데이트
    tags = []
    for tag, tweet_count in results:
        tag.tweet_count = tweet_count
        tags.append(tag)
    
    return tags

@router.get("/tags/{tag_name}/tweets")
def get_tag_tweets(
    tag_name: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    특정 태그의 트윗 목록을 조회합니다.
    
    Args:
        tag_name: 태그 이름
        skip: 건너뛸 트윗 수
        limit: 조회할 트윗 수
        db: 데이터베이스 세션
    
    Returns:
        dict: 태그 정보와 트윗 목록
    
    Raises:
        HTTPException: 태그를 찾을 수 없는 경우
    """
    # 태그 조회
    tag = db.query(Tag).filter(Tag.name == tag_name.lower()).first()
    if not tag:
        raise HTTPException(
            status_code=404,
            detail=f"태그 '{tag_name}'을(를) 찾을 수 없습니다."
        )
    
    # 해당 태그의 트윗 조회
    tweets = db.query(Tweet)\
        .join(Tweet.tags)\
        .filter(Tag.id == tag.id)\
        .order_by(Tweet.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    # 전체 트윗 수
    total = db.query(Tweet)\
        .join(Tweet.tags)\
        .filter(Tag.id == tag.id)\
        .count()
    
    return {
        "tag": tag,
        "tweets": tweets,
        "total": total,
        "page": (skip // limit) + 1,
        "size": limit
    }

@router.get("/tags/popular")
def get_popular_tags(
    days: int = Query(7, description="최근 N일간의 인기 태그"),
    limit: int = Query(10, ge=1, le=50, description="조회할 태그 수"),
    db: Session = Depends(get_db)
):
    """
    최근 인기 태그를 조회합니다.
    
    Args:
        days: 집계 기간 (일)
        limit: 조회할 태그 수
        db: 데이터베이스 세션
    
    Returns:
        List[dict]: 인기 태그 목록
    """
    from datetime import datetime, timedelta
    
    # 집계 시작 날짜
    since_date = datetime.now() - timedelta(days=days)
    
    # 최근 N일간 가장 많이 사용된 태그
    popular_tags = db.query(
        Tag.name,
        func.count(Tweet.id).label('usage_count')
    ).join(tweet_tags)\
    .join(Tweet)\
    .filter(Tweet.created_at >= since_date)\
    .group_by(Tag.id, Tag.name)\
    .order_by(desc('usage_count'))\
    .limit(limit)\
    .all()
    
    return [
        {
            "name": tag_name,
            "count": usage_count,
            "usage_count": usage_count,  # 호환성을 위해 둘 다 제공
            "period_days": days
        }
        for tag_name, usage_count in popular_tags
    ]

@router.delete("/tags/{tag_name}")
def delete_tag(
    tag_name: str,
    db: Session = Depends(get_db)
):
    """
    태그를 비활성화합니다 (관리자 전용)
    
    Args:
        tag_name: 태그 이름
        db: 데이터베이스 세션
    
    Returns:
        dict: 성공 메시지
    
    Raises:
        HTTPException: 태그를 찾을 수 없는 경우
    """
    # 태그 조회
    tag = db.query(Tag).filter(Tag.name == tag_name.lower()).first()
    if not tag:
        raise HTTPException(
            status_code=404,
            detail=f"태그 '{tag_name}'을(를) 찾을 수 없습니다."
        )
    
    # 비활성화
    tag.is_active = False
    db.commit()
    
    return {"message": f"태그 '{tag_name}'이(가) 비활성화되었습니다."}