"""
API 연결 및 기능 테스트 스크립트
"""

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")

def test_api_connection():
    """기본 API 연결 테스트"""
    try:
        print("🔍 API 연결 테스트...")
        response = requests.get(f"{API_BASE_URL.replace('/api', '')}/health", timeout=10)
        print(f"✅ Health Check: {response.status_code} - {response.text}")
        return True
    except requests.exceptions.ConnectionError:
        print(f"❌ API 서버에 연결할 수 없습니다: {API_BASE_URL}")
        print("💡 서버가 실행 중인지 확인하세요: python run_server.py")
        return False
    except Exception as e:
        print(f"❌ 연결 오류: {e}")
        return False

def test_user_creation():
    """테스트 사용자 생성"""
    try:
        print("\n👤 테스트 사용자 생성...")
        user_data = {
            "telegram_id": 99999999,
            "telegram_username": "debug_user",
            "display_name": "디버그 사용자"
        }
        
        response = requests.post(f"{API_BASE_URL}/users", json=user_data, timeout=10)
        print(f"사용자 생성 응답: {response.status_code}")
        print(f"응답 내용: {response.text}")
        
        if response.status_code in [200, 201]:
            print("✅ 사용자 생성 성공")
            return user_data["telegram_id"]
        else:
            print("❌ 사용자 생성 실패")
            return None
    except Exception as e:
        print(f"❌ 사용자 생성 오류: {e}")
        return None

def test_tweet_creation(user_id):
    """테스트 트윗 생성"""
    try:
        print(f"\n🐦 테스트 트윗 생성 (사용자 ID: {user_id})...")
        tweet_data = {
            "user_id": user_id,
            "tweet_url": "https://twitter.com/test/status/1234567890123456789",
            "tags": ["test", "debug"],
            "comment": "디버그 테스트 트윗입니다"
        }
        
        response = requests.post(f"{API_BASE_URL}/tweets", json=tweet_data, timeout=10)
        print(f"트윗 생성 응답: {response.status_code}")
        print(f"응답 내용: {response.text}")
        
        if response.status_code == 200:
            print("✅ 트윗 생성 성공")
            data = response.json()
            return data.get("id")
        else:
            print("❌ 트윗 생성 실패")
            return None
    except Exception as e:
        print(f"❌ 트윗 생성 오류: {e}")
        return None

def test_user_tweets(user_id):
    """사용자 트윗 조회 테스트"""
    try:
        print(f"\n📋 사용자 트윗 조회 (사용자 ID: {user_id})...")
        response = requests.get(f"{API_BASE_URL}/users/{user_id}/tweets", timeout=10)
        print(f"트윗 조회 응답: {response.status_code}")
        print(f"응답 내용: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            tweet_count = len(data.get("tweets", []))
            print(f"✅ 트윗 조회 성공 - {tweet_count}개 트윗 발견")
            return True
        else:
            print("❌ 트윗 조회 실패")
            return False
    except Exception as e:
        print(f"❌ 트윗 조회 오류: {e}")
        return False

def test_all_endpoints():
    """모든 엔드포인트 테스트"""
    try:
        print("\n🔍 전체 엔드포인트 테스트...")
        
        endpoints = [
            "/tweets",
            "/users",
            "/tags",
            "/stats"
        ]
        
        for endpoint in endpoints:
            try:
                response = requests.get(f"{API_BASE_URL}{endpoint}", timeout=10)
                print(f"  {endpoint}: {response.status_code}")
            except Exception as e:
                print(f"  {endpoint}: 오류 - {e}")
                
    except Exception as e:
        print(f"❌ 엔드포인트 테스트 오류: {e}")

def main():
    print("🚀 Yapper Dash API 디버깅 시작")
    print(f"📍 API URL: {API_BASE_URL}")
    print("=" * 50)
    
    # 1. 기본 연결 테스트
    if not test_api_connection():
        return
    
    # 2. 엔드포인트 테스트
    test_all_endpoints()
    
    # 3. 사용자 생성 테스트
    user_id = test_user_creation()
    if not user_id:
        print("\n❌ 사용자 생성 실패로 추가 테스트를 건너뜁니다.")
        return
    
    # 4. 트윗 생성 테스트
    tweet_id = test_tweet_creation(user_id)
    
    # 5. 트윗 조회 테스트
    test_user_tweets(user_id)
    
    print("\n🎉 디버깅 테스트 완료!")
    print("\n💡 만약 문제가 있다면:")
    print("  1. API 서버가 실행 중인지 확인 (python run_server.py)")
    print("  2. 데이터베이스가 초기화되었는지 확인 (python init_db.py)")
    print("  3. .env 파일에 올바른 설정이 있는지 확인")

if __name__ == "__main__":
    main()