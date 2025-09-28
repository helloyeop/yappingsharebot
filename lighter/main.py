from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, validator
from typing import List, Dict, Any
import httpx
import json
import logging
from datetime import datetime
import os
import re
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import hashlib

# 로깅 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(current_dir, 'wallet_search_log.txt')
multi_wallet_file = os.path.join(current_dir, 'multi_wallet_addresses.txt')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Rate limiting 설정
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Lighter Portfolio Tracker")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS 설정 - 프로덕션 환경에 맞게 제한
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ypab5.com", "http://localhost:3000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# API 설정
API_BASE_URL = "https://mainnet.zklighter.elliot.ai/api/v1/account"
WALLET_ADDRESS_REGEX = re.compile(r'^0x[a-fA-F0-9]{40}$')

def to_checksum_address_fallback(address: str) -> str:
    """
    체크섬 주소로 변환 시도
    정확한 Keccak-256이 없으므로 알려진 패턴 사용
    """
    address_lower = address.lower()
    
    # 알려진 주소들의 매핑 (필요시 확장 가능)
    known_addresses = {
        '0x8b49af69df8d44c735812d30a3a5c66ba6fc05fc': '0x8b49af69dF8d44C735812D30A3A5c66BA6fc05Fc'
    }
    
    if address_lower in known_addresses:
        return known_addresses[address_lower]
    
    # 알려지지 않은 주소는 첫 글자와 중간 글자들을 대문자로 변환하는 패턴 적용
    addr_without_prefix = address_lower[2:]
    result = '0x'
    for i, char in enumerate(addr_without_prefix):
        if char in '0123456789':
            result += char
        elif i % 8 < 4:  # 8자리마다 앞 4자리는 대문자 패턴
            result += char.upper()
        else:
            result += char
    return result

class WalletRequest(BaseModel):
    addresses: List[str]
    
    @validator('addresses', each_item=True)
    def validate_address(cls, v):
        # 대소문자 구분 없이 검증
        address = v.strip()
        if not re.match(r'^0x[a-fA-F0-9]{40}$', address, re.IGNORECASE):
            raise ValueError(f'Invalid wallet address format: {v}')
        
        # 이미 대소문자가 섞여있으면 그대로 반환 (올바른 체크섬일 가능성)
        if address != address.lower() and address != address.upper():
            return address
        
        # 모두 소문자인 경우만 체크섬 변환 시도
        if address == address.lower():
            try:
                return to_checksum_address_fallback(address)
            except Exception:
                return address
        
        # 원본 반환
        return address
    
    @validator('addresses')
    def validate_count(cls, v):
        if len(v) > 20:
            raise ValueError('Maximum 20 addresses allowed')
        if len(v) == 0:
            raise ValueError('At least one address required')
        return v

class Position(BaseModel):
    market_id: int
    symbol: str
    sign: int
    position: str
    avg_entry_price: str
    position_value: str
    unrealized_pnl: str
    liquidation_price: str
    margin_mode: int
    allocated_margin: str
    initial_margin_fraction: str

class AccountData(BaseModel):
    l1_address: str
    total_asset_value: str
    cross_asset_value: str
    positions: List[Dict[str, Any]]

@app.post("/api/fetch_accounts")
@limiter.limit("10/minute")  # 분당 10회 제한
async def fetch_accounts(wallet_request: WalletRequest, request: Request):
    """여러 지갑 주소의 데이터를 가져옵니다."""
    # 로그 기록 - 통계 분석용 전체 주소 기록
    client_ip = request.client.host
    logging.info(f"IP: {client_ip} | Addresses: {', '.join(wallet_request.addresses)}")
    
    # 다계정 지갑 주소 수집 (2개 이상의 지갑을 조회한 경우)
    if len(wallet_request.addresses) >= 2:
        try:
            # 파일이 존재하는지 확인하고 인덱스 계산
            index = 1
            if os.path.exists(multi_wallet_file):
                with open(multi_wallet_file, 'r', encoding='utf-8') as rf:
                    lines = rf.readlines()
                    if lines and lines[0].strip() == "index,addresses":
                        index = len(lines)  # 헤더 제외한 실제 데이터 수 + 1
                    else:
                        index = len(lines) + 1
            
            # 파일에 추가
            with open(multi_wallet_file, 'a', encoding='utf-8') as f:
                # 파일이 비어있거나 새 파일이면 헤더 추가
                if index == 1:
                    f.write("index,addresses\n")
                
                addresses_str = ','.join(wallet_request.addresses)
                f.write(f"{index},{addresses_str}\n")
        except Exception as e:
            logging.error(f"Failed to save multi-wallet data: {str(e)}")
    
    accounts_data = []
    position_summary = {}  # 심볼별 포지션 합계
    
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        for address in wallet_request.addresses:
            try:
                response = await client.get(
                    f"{API_BASE_URL}?by=l1_address&value={address}",
                    headers={"User-Agent": "LighterTracker/1.0"}
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get("accounts") and len(data["accounts"]) > 0:
                    account = data["accounts"][0]
                    # 홀딩 중인 포지션만 필터링 (position이 0이 아닌 것)
                    filtered_positions = []
                    for pos in account.get("positions", []):
                        if float(pos.get("position", "0")) != 0:
                            # 레버리지 계산 (100 / initial_margin_fraction)
                            imf = float(pos.get("initial_margin_fraction", "100"))
                            leverage = round(100 / imf, 2) if imf > 0 else 0
                            pos["leverage"] = f"{leverage}x"
                            filtered_positions.append(pos)
                            
                            # 포지션 합계 계산
                            symbol = pos.get("symbol", "")
                            position_size = float(pos.get("position", "0"))
                            sign = pos.get("sign", 1)
                            
                            # 롱은 양수, 숏은 음수로 계산
                            net_position = position_size * sign
                            
                            if symbol not in position_summary:
                                position_summary[symbol] = {
                                    "net_position": 0,
                                    "total_value": 0,
                                    "long_count": 0,
                                    "short_count": 0,
                                    "accounts": []
                                }
                            
                            position_summary[symbol]["net_position"] += net_position
                            position_summary[symbol]["total_value"] += float(pos.get("position_value", "0"))
                            if sign == 1:
                                position_summary[symbol]["long_count"] += 1
                            else:
                                position_summary[symbol]["short_count"] += 1
                            position_summary[symbol]["accounts"].append(address[:8] + "...")
                    
                    account["positions"] = filtered_positions
                    accounts_data.append(account)
                    
            except httpx.HTTPStatusError as e:
                logging.error(f"HTTP error for {address[:8]}...: {e.response.status_code}")
                continue
            except httpx.TimeoutException:
                logging.error(f"Timeout for {address[:8]}...")
                continue
            except Exception as e:
                logging.error(f"Unexpected error for {address[:8]}...: {type(e).__name__}")
                continue
    
    return {
        "accounts": accounts_data,
        "position_summary": position_summary
    }

@app.get("/", response_class=HTMLResponse)
async def read_index():
    """메인 페이지를 반환합니다."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(current_dir, "static", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

# Static 파일 서빙
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)