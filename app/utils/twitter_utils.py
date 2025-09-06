import re
from typing import Optional
from urllib.parse import urlparse

def extract_tweet_id_from_url(tweet_url: str) -> Optional[str]:
    """
    트위터 URL에서 트윗 ID를 추출합니다.
    
    예시 URL들:
    - https://twitter.com/user/status/1234567890
    - https://x.com/user/status/1234567890  
    - https://mobile.twitter.com/user/status/1234567890
    
    Args:
        tweet_url: 트위터 URL
        
    Returns:
        str: 트윗 ID (숫자), 실패시 None
    """
    # URL에서 트윗 ID를 찾는 정규표현식
    # status/ 뒤의 숫자 부분을 찾습니다
    pattern = r'(?:twitter\.com|x\.com|mobile\.twitter\.com)/.+/status/(\d+)'
    
    match = re.search(pattern, tweet_url)
    if match:
        return match.group(1)  # 첫 번째 그룹 (트윗 ID)
    
    return None

def validate_twitter_url(tweet_url: str) -> bool:
    """
    트위터 URL이 유효한지 확인합니다.
    
    Args:
        tweet_url: 검증할 URL
        
    Returns:
        bool: 유효하면 True, 아니면 False
    """
    if not tweet_url:
        return False
    
    # 기본적인 URL 형식 검증
    try:
        parsed = urlparse(tweet_url)
        if not parsed.scheme or not parsed.netloc:
            return False
    except:
        return False
    
    # 트윗 ID가 추출되는지 확인
    tweet_id = extract_tweet_id_from_url(tweet_url)
    return tweet_id is not None

def normalize_twitter_url(tweet_url: str) -> str:
    """
    트위터 URL을 표준 형식으로 변환합니다.
    
    Args:
        tweet_url: 원본 URL
        
    Returns:
        str: 표준화된 URL
    """
    tweet_id = extract_tweet_id_from_url(tweet_url)
    if not tweet_id:
        return tweet_url
    
    # URL에서 사용자명 추출
    pattern = r'(?:twitter\.com|x\.com|mobile\.twitter\.com)/([^/]+)/status/\d+'
    match = re.search(pattern, tweet_url)
    username = match.group(1) if match else "user"
    
    # 표준 형식으로 변환 (twitter.com 사용)
    return f"https://twitter.com/{username}/status/{tweet_id}"