"""
데이터베이스 초기화 스크립트

이 스크립트는 다음을 수행합니다:
1. 데이터베이스 테이블 생성
2. 기본 데이터 삽입 (선택사항)
3. 연결 테스트
"""

import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 프로젝트 루트를 Python path에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.models import Base, User, Tweet, Tag
from app.db.database import DATABASE_URL, engine
from config import settings

def create_tables():
    """데이터베이스 테이블을 생성합니다."""
    try:
        print("🔧 데이터베이스 테이블 생성 중...")
        Base.metadata.create_all(bind=engine)
        print("✅ 테이블 생성 완료!")
        return True
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")
        return False

def test_connection():
    """데이터베이스 연결을 테스트합니다."""
    try:
        print("🔍 데이터베이스 연결 테스트 중...")
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            if result.fetchone():
                print("✅ 데이터베이스 연결 성공!")
                return True
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        print("💡 다음을 확인하세요:")
        print("   - PostgreSQL이 실행 중인지")
        print("   - DATABASE_URL이 올바른지")
        print("   - 데이터베이스와 사용자 권한이 있는지")
        return False

def create_sample_data():
    """샘플 데이터를 생성합니다 (테스트용)."""
    try:
        from app.db.database import SessionLocal
        db = SessionLocal()
        
        print("📝 샘플 데이터 생성 중...")
        
        # 샘플 사용자 생성
        sample_user = User(
            telegram_id=12345678,
            telegram_username="sample_user",
            display_name="샘플 사용자"
        )
        
        # 사용자가 이미 존재하는지 확인
        existing_user = db.query(User).filter(User.telegram_id == 12345678).first()
        if not existing_user:
            db.add(sample_user)
            db.commit()
            print("✅ 샘플 사용자 생성됨: @sample_user")
        else:
            print("ℹ️  샘플 사용자가 이미 존재함")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ 샘플 데이터 생성 실패: {e}")
        return False

def show_table_info():
    """생성된 테이블 정보를 출력합니다."""
    try:
        print("\n📊 생성된 테이블 정보:")
        with engine.connect() as connection:
            # SQLite와 PostgreSQL 모두 지원
            if DATABASE_URL.startswith("sqlite"):
                # SQLite에서 테이블 목록 조회
                result = connection.execute(text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' 
                    ORDER BY name;
                """))
            else:
                # PostgreSQL에서 테이블 목록 조회
                result = connection.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """))
            
            tables = result.fetchall()
            for table in tables:
                print(f"   📋 {table[0]}")
                
            print(f"\n✅ 총 {len(tables)}개의 테이블이 생성되었습니다.")
            
    except Exception as e:
        print(f"❌ 테이블 정보 조회 실패: {e}")

def main():
    """메인 초기화 함수"""
    print("🚀 Yapper Dash 데이터베이스 초기화 시작")
    print(f"📍 데이터베이스 URL: {DATABASE_URL}")
    print("-" * 50)
    
    # 1. 연결 테스트
    if not test_connection():
        print("\n❌ 데이터베이스 연결에 실패했습니다. 초기화를 중단합니다.")
        sys.exit(1)
    
    # 2. 테이블 생성
    if not create_tables():
        print("\n❌ 테이블 생성에 실패했습니다.")
        sys.exit(1)
    
    # 3. 테이블 정보 출력
    show_table_info()
    
    # 4. 샘플 데이터 생성 (선택사항)
    response = input("\n❓ 샘플 데이터를 생성하시겠습니까? (y/N): ").lower()
    if response == 'y':
        create_sample_data()
    
    print("\n🎉 데이터베이스 초기화가 완료되었습니다!")
    print("\n📝 다음 단계:")
    print("   1. .env 파일에 올바른 설정값 입력")
    print("   2. FastAPI 서버 실행: python main.py")
    print("   3. 텔레그램 봇 실행: python bot.py")

if __name__ == "__main__":
    main()