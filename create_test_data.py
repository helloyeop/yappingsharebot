"""
테스트 데이터 생성 스크립트
API 테스트를 위한 샘플 데이터를 생성합니다.
"""

import sys
import os
import random
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal, create_tables
from app.models.models import User, Tweet, Tag
from app.utils.database_utils import get_or_create_user, get_or_create_tag

# 샘플 데이터
SAMPLE_USERS = [
    {"id": 11111111, "username": "alice_crypto", "name": "Alice 🚀"},
    {"id": 22222222, "username": "bob_trader", "name": "Bob"},
    {"id": 33333333, "username": "charlie_dev", "name": "Charlie Dev"},
    {"id": 44444444, "username": "david_news", "name": "David"},
    {"id": 55555555, "username": "eve_analyst", "name": "Eve 분석가"},
]

SAMPLE_TAGS = [
    "bitcoin", "ethereum", "defi", "nft", "web3",
    "crypto", "blockchain", "trading", "analysis", "news",
    "개발", "업데이트", "에어드랍", "거래소", "규제"
]

SAMPLE_COMMENTS = [
    "정말 유용한 정보네요!",
    "이거 꼭 확인해보세요",
    "대박 소식입니다 🚀",
    "중요한 업데이트",
    "모두 주목!",
    "개발 진행 상황 공유합니다",
    "시장 분석 자료",
    "새로운 프로젝트 발견",
    "규제 관련 뉴스",
    "기술적 분석 차트",
    None,  # 코멘트 없음
    None
]

def create_test_data():
    """테스트 데이터를 생성합니다."""
    print("🔧 테스트 데이터 생성 시작...")
    
    # 데이터베이스 테이블 생성
    create_tables()
    
    db = SessionLocal()
    
    try:
        # 1. 사용자 생성
        print("\n👥 사용자 생성 중...")
        users = []
        for user_data in SAMPLE_USERS:
            user = get_or_create_user(
                db,
                telegram_id=user_data["id"],
                telegram_username=user_data["username"],
                display_name=user_data["name"]
            )
            users.append(user)
            print(f"   ✅ {user.telegram_username} ({user.display_name})")
        
        # 2. 태그 생성
        print("\n🏷️ 태그 생성 중...")
        tags = []
        for tag_name in SAMPLE_TAGS:
            tag = get_or_create_tag(db, tag_name)
            tags.append(tag)
            print(f"   ✅ #{tag.name}")
        
        # 3. 트윗 생성
        print("\n🐦 트윗 생성 중...")
        tweet_count = 0
        
        # 각 사용자별로 랜덤한 수의 트윗 생성
        for user in users:
            num_tweets = random.randint(3, 15)  # 사용자당 3~15개 트윗
            
            for i in range(num_tweets):
                # 랜덤 날짜 (최근 30일 이내)
                days_ago = random.randint(0, 30)
                hours_ago = random.randint(0, 23)
                created_at = datetime.now() - timedelta(days=days_ago, hours=hours_ago)
                
                # 랜덤 트윗 ID (실제로는 유효하지 않은 ID)
                tweet_id = f"{random.randint(1000000000000000000, 9999999999999999999)}"
                
                # 랜덤 태그 선택 (1~3개)
                selected_tags = random.sample(tags, k=random.randint(1, 3))
                
                # 랜덤 코멘트
                comment = random.choice(SAMPLE_COMMENTS)
                
                # 트윗 생성
                tweet = Tweet(
                    user_id=user.telegram_id,
                    tweet_url=f"https://twitter.com/{user.telegram_username}/status/{tweet_id}",
                    tweet_id=tweet_id,
                    comment=comment,
                    content_preview=f"샘플 트윗 내용 - {user.display_name}의 {i+1}번째 트윗",
                    created_at=created_at
                )
                
                # 태그 연결
                for tag in selected_tags:
                    tweet.tags.append(tag)
                
                db.add(tweet)
                tweet_count += 1
        
        # 커밋
        db.commit()
        print(f"\n✅ 총 {tweet_count}개의 트윗이 생성되었습니다!")
        
        # 4. 통계 출력
        print("\n📊 생성된 데이터 통계:")
        print(f"   - 사용자: {len(users)}명")
        print(f"   - 태그: {len(tags)}개")
        print(f"   - 트윗: {tweet_count}개")
        
        # 사용자별 트윗 수
        print("\n📈 사용자별 트윗 수:")
        for user in users:
            user_tweet_count = db.query(Tweet).filter(Tweet.user_id == user.telegram_id).count()
            print(f"   - {user.telegram_username}: {user_tweet_count}개")
        
        print("\n🎉 테스트 데이터 생성 완료!")
        print("\n💡 테스트해볼 수 있는 API 엔드포인트:")
        print("   - GET /api/tweets - 전체 트윗 조회")
        print("   - GET /api/tweets?tag=bitcoin - 특정 태그 필터")
        print("   - GET /api/tweets?user_id=11111111 - 특정 사용자 필터")
        print("   - GET /api/tags - 태그 목록")
        print("   - GET /api/users - 사용자 목록")
        print("   - GET /api/stats - 통계 정보")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        db.rollback()
    finally:
        db.close()

def reset_database():
    """데이터베이스를 초기화합니다."""
    response = input("\n⚠️ 모든 데이터가 삭제됩니다. 계속하시겠습니까? (y/N): ")
    if response.lower() != 'y':
        print("취소되었습니다.")
        return
    
    try:
        # SQLite 파일 삭제
        if os.path.exists("yapper_dash.db"):
            os.remove("yapper_dash.db")
            print("✅ 데이터베이스가 초기화되었습니다.")
        else:
            print("ℹ️ 데이터베이스 파일이 없습니다.")
    except Exception as e:
        print(f"❌ 초기화 실패: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="테스트 데이터 관리")
    parser.add_argument("--reset", action="store_true", help="데이터베이스 초기화")
    args = parser.parse_args()
    
    if args.reset:
        reset_database()
    else:
        create_test_data()