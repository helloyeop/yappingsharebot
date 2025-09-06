"""
SQLite 설정 테스트 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import engine, SessionLocal
from app.models.models import User, Tweet, Tag

def test_sqlite():
    print("🔍 SQLite 데이터베이스 테스트 시작...")
    
    # 1. 연결 테스트
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ 데이터베이스 연결 성공!")
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        return False
    
    # 2. 테이블 생성 테스트
    try:
        from app.db.database import create_tables
        create_tables()
        print("✅ 테이블 생성 성공!")
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")
        return False
    
    # 3. 데이터 추가 테스트
    try:
        db = SessionLocal()
        
        # 테스트 사용자 생성
        test_user = User(
            telegram_id=99999999,
            telegram_username="test_user",
            display_name="테스트 사용자"
        )
        
        existing = db.query(User).filter(User.telegram_id == 99999999).first()
        if not existing:
            db.add(test_user)
            db.commit()
            print("✅ 테스트 데이터 추가 성공!")
        else:
            print("ℹ️  테스트 사용자가 이미 존재합니다")
        
        # 사용자 조회 테스트
        users = db.query(User).all()
        print(f"✅ 전체 사용자 수: {len(users)}명")
        
        db.close()
        
    except Exception as e:
        print(f"❌ 데이터 작업 실패: {e}")
        return False
    
    print("\n🎉 SQLite 설정 완료! 데이터베이스를 사용할 준비가 되었습니다.")
    print(f"📍 데이터베이스 파일: {os.path.abspath('yapper_dash.db')}")
    return True

if __name__ == "__main__":
    test_sqlite()