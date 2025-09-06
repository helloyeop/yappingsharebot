from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.models.models import Base
import os
from dotenv import load_dotenv

load_dotenv()

# SQLite를 기본으로 사용 (파일 기반 데이터베이스)
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "sqlite:///./yapper_dash.db"  # 현재 디렉토리에 yapper_dash.db 파일 생성
)

# SQLite 연결 설정
if DATABASE_URL.startswith("sqlite"):
    # SQLite는 check_same_thread=False 필요 (FastAPI 멀티스레드 환경)
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL 등 다른 DB 사용시
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    Base.metadata.create_all(bind=engine)