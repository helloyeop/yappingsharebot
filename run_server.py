"""
FastAPI 서버 실행 스크립트
"""

import uvicorn

if __name__ == "__main__":
    print("🚀 FastAPI 서버를 시작합니다...")
    print("📍 웹 대시보드: http://localhost:8000")
    print("📍 API 문서: http://localhost:8000/docs")
    print("🛑 종료하려면 Ctrl+C를 누르세요\n")
    
    uvicorn.run(
        "main:app",  # 문자열로 앱 지정 (reload 사용시 필요)
        host="0.0.0.0",
        port=8000,
        reload=True,  # 개발 모드에서 자동 리로드
        log_level="info"
    )