"""
간단한 서버 실행 스크립트 (문제 해결용)
"""

import os
import sys

# 프로젝트 루트 디렉토리를 Python path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("🔍 필수 패키지 확인 중...")
    
    # 필수 패키지 import 테스트
    import fastapi
    print("✅ FastAPI 확인")
    
    import uvicorn  
    print("✅ Uvicorn 확인")
    
    import jinja2
    print("✅ Jinja2 확인")
    
    import sqlalchemy
    print("✅ SQLAlchemy 확인")
    
    print("🚀 서버 시작 중...")
    
    # 앱 import
    from main import app
    print("✅ 앱 로드 완료")
    
    # 서버 실행
    print("📍 웹 대시보드: http://localhost:8000")
    print("📍 API 문서: http://localhost:8000/docs")
    print("🛑 종료하려면 Ctrl+C를 누르세요\n")
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=False,  # reload 비활성화로 문제 방지
        log_level="info"
    )
    
except ImportError as e:
    print(f"❌ 패키지 import 실패: {e}")
    print("💡 다음 명령어를 실행해보세요:")
    print("   pip install -r requirements.txt")
    
except Exception as e:
    print(f"❌ 서버 시작 실패: {e}")
    print("💡 오류 해결 방법:")
    print("   1. .env 파일 설정 확인")
    print("   2. 데이터베이스 연결 확인")
    print("   3. python init_db.py 실행")