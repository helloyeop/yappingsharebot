#!/usr/bin/env python3
"""
핵심 태그 초기화 스크립트
처음 실행 시 기본 태그들을 데이터베이스에 추가합니다.
"""

import os
import sys
from dotenv import load_dotenv

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal
from app.models.models import Tag

load_dotenv()

# 핵심 태그 목록
CORE_TAGS = ["crypto", "eth", "btc", "defi", "nft", "web3", "trading", "market"]

def init_core_tags():
    """핵심 태그를 데이터베이스에 추가합니다."""
    db = SessionLocal()
    
    try:
        for tag_name in CORE_TAGS:
            # 이미 존재하는지 확인
            existing_tag = db.query(Tag).filter(Tag.name == tag_name).first()
            
            if not existing_tag:
                # 새 태그 생성
                new_tag = Tag(
                    name=tag_name,
                    is_active=True,
                    is_core=True,
                    created_by=None  # 시스템 생성
                )
                db.add(new_tag)
                print(f"✅ 핵심 태그 '{tag_name}' 추가됨")
            else:
                # 기존 태그를 핵심 태그로 업데이트
                existing_tag.is_core = True
                existing_tag.is_active = True
                print(f"📌 태그 '{tag_name}'을(를) 핵심 태그로 설정")
        
        db.commit()
        print("\n🎉 핵심 태그 초기화 완료!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🏷️ 핵심 태그 초기화 시작...")
    init_core_tags()