"""
텔레그램 봇 실행 스크립트
"""

import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

def check_env_variables():
    """필수 환경변수가 설정되어 있는지 확인"""
    required_vars = {
        'TELEGRAM_BOT_TOKEN': '텔레그램 봇 토큰',
        'DATABASE_URL': '데이터베이스 URL',
        'API_BASE_URL': 'API 베이스 URL'
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"  - {var}: {description}")
    
    if missing_vars:
        print("❌ 다음 환경변수가 설정되지 않았습니다:")
        print("\n".join(missing_vars))
        print("\n💡 .env 파일을 생성하고 필요한 값들을 설정해주세요.")
        print("📝 .env.example 파일을 참고하세요.")
        return False
    
    return True

if __name__ == "__main__":
    print("🤖 Telegram Bot을 시작합니다...")
    
    # 환경변수 체크
    if not check_env_variables():
        exit(1)
    
    print("✅ 환경변수 확인 완료")
    print("🔗 API 서버와 연결 중...")
    print("🛑 봇을 종료하려면 Ctrl+C를 누르세요\n")
    
    # 봇 실행
    from bot import TwitterBot
    
    try:
        bot = TwitterBot()
        bot.run()
    except KeyboardInterrupt:
        print("\n🛑 봇이 종료되었습니다.")
    except Exception as e:
        print(f"\n❌ 봇 실행 중 오류 발생: {e}")
        print("💡 로그를 확인하고 설정을 점검해주세요.")