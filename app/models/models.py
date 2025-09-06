from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

Base = declarative_base()

tweet_tags = Table(
    'tweet_tags',
    Base.metadata,
    Column('tweet_id', UUID(as_uuid=True), ForeignKey('tweets.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)

class User(Base):
    __tablename__ = "users"
    
    telegram_id = Column(Integer, primary_key=True, index=True)
    telegram_username = Column(String(255), unique=True, index=True)
    display_name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    tweets = relationship("Tweet", back_populates="user")

class Tweet(Base):
    __tablename__ = "tweets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Integer, ForeignKey("users.telegram_id"), index=True)
    tweet_url = Column(String(500), nullable=False)
    tweet_id = Column(String(50), unique=True, index=True)
    content_preview = Column(Text)
    image_url = Column(String(500))
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="tweets")
    tags = relationship("Tag", secondary=tweet_tags, back_populates="tweets")

class Tag(Base):
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    tweet_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)  # 활성/비활성 상태
    is_core = Column(Boolean, default=False)  # 핵심 태그 여부 (초기 태그)
    created_by = Column(Integer, ForeignKey("users.telegram_id"), nullable=True)  # 생성한 사용자
    
    tweets = relationship("Tweet", secondary=tweet_tags, back_populates="tags")
    creator = relationship("User", foreign_keys=[created_by])