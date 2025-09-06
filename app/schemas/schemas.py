from pydantic import BaseModel, HttpUrl
from datetime import datetime
from uuid import UUID
from typing import List, Optional

class UserBase(BaseModel):
    telegram_username: str
    display_name: str

class UserCreate(UserBase):
    telegram_id: int

class User(UserBase):
    telegram_id: int
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True

class TagBase(BaseModel):
    name: str

class TagCreate(TagBase):
    pass

class Tag(TagBase):
    id: int
    created_at: datetime
    tweet_count: int
    is_active: bool = True
    is_core: bool = False

    class Config:
        from_attributes = True

class TweetBase(BaseModel):
    tweet_url: str
    comment: Optional[str] = None

class TweetCreate(TweetBase):
    user_id: int
    tags: Optional[List[str]] = []

class Tweet(TweetBase):
    id: UUID
    user_id: int
    tweet_id: str
    content_preview: Optional[str]
    image_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    user: User
    tags: List[Tag]

    class Config:
        from_attributes = True

class TweetResponse(BaseModel):
    tweets: List[Tweet]
    total: int
    page: int
    size: int

class StatsResponse(BaseModel):
    total_tweets: int
    total_users: int
    total_tags: int
    tweets_today: int
    most_active_user: Optional[str]