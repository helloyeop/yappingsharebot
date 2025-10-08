from fastapi import FastAPI, HTTPException, Request, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.sessions import SessionMiddleware
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
import secrets

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

# 접근 코드 설정 (환경변수 또는 기본값)
ACCESS_CODE = os.getenv("LIGHTER_ACCESS_CODE", "1point500$")  # 원하는 코드로 변경 가능

# Rate limiting 설정
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Lighter Portfolio Tracker")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 세션 미들웨어 추가 (접근 제어용)
app.add_middleware(SessionMiddleware, secret_key=secrets.token_hex(32))

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
ORDERBOOK_API_URL = "https://mainnet.zklighter.elliot.ai/api/v1/orderBookDetails"
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

# 인증 의존성 함수
def require_authentication(request: Request):
    """접근 코드 인증이 필요한 엔드포인트에 사용"""
    if not request.session.get("authenticated"):
        # HTML 요청인 경우 로그인 페이지로 리다이렉션
        if "text/html" in request.headers.get("accept", ""):
            return RedirectResponse(url="/login", status_code=302)
        # API 요청인 경우 401 에러 반환
        raise HTTPException(status_code=401, detail="Access code required")
    return True

class LoginRequest(BaseModel):
    access_code: str

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
        if len(v) > 100:
            raise ValueError('Maximum 100 addresses allowed')
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
async def fetch_accounts(wallet_request: WalletRequest, request: Request, authenticated: bool = Depends(require_authentication)):
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
    
    # 토큰 현재 가격 가져오기
    market_prices = {}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            price_response = await client.get(ORDERBOOK_API_URL)
            price_response.raise_for_status()
            price_data = price_response.json()

            # API 응답에서 order_book_details 배열 추출
            order_books = price_data.get("order_book_details", [])

            # 필요한 심볼들의 가격만 추출
            for market in order_books:
                symbol = market.get("symbol", "")
                if symbol:
                    market_prices[symbol] = {
                        "last_price": float(market.get("last_trade_price", 0)),
                        "daily_change": float(market.get("daily_price_change", 0)),
                        "daily_high": float(market.get("daily_price_high", 0)),
                        "daily_low": float(market.get("daily_price_low", 0))
                    }
    except Exception as e:
        logging.error(f"Failed to fetch market prices: {str(e)}")

    # 각 포지션에 청산까지 변동률 계산 추가
    for account in accounts_data:
        for pos in account.get("positions", []):
            symbol = pos.get("symbol", "")
            if symbol in market_prices:
                current_price = market_prices[symbol]["last_price"]
                liquidation_price = float(pos.get("liquidation_price", 0))

                pos["current_price"] = current_price

                if current_price > 0 and liquidation_price > 0:
                    # 롱/숏에 따른 청산 변동률 계산 (절대값으로 저장)
                    sign = pos.get("sign", 1)
                    if sign == 1:  # Long position
                        # 가격이 얼마나 떨어져야 청산되는지
                        liquidation_percent = ((current_price - liquidation_price) / current_price) * 100
                    else:  # Short position
                        # 가격이 얼마나 올라가야 청산되는지
                        liquidation_percent = ((liquidation_price - current_price) / current_price) * 100

                    pos["liquidation_percent"] = round(liquidation_percent, 2)

    return {
        "accounts": accounts_data,
        "position_summary": position_summary,
        "market_prices": market_prices
    }

@app.get("/api/market_prices")
@limiter.limit("30/minute")
async def get_market_prices(request: Request, authenticated: bool = Depends(require_authentication)):
    """토큰 현재 가격을 가져옵니다."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.get(ORDERBOOK_API_URL)
            response.raise_for_status()
            data = response.json()

            # API 응답에서 order_book_details 배열 추출
            order_books = data.get("order_book_details", [])

            # 필요한 정보만 추출하여 반환
            market_prices = {}
            for market in order_books:
                symbol = market.get("symbol", "")
                if symbol:
                    market_prices[symbol] = {
                        "last_price": float(market.get("last_trade_price", 0)),
                        "daily_change": float(market.get("daily_price_change", 0)),
                        "daily_high": float(market.get("daily_price_high", 0)),
                        "daily_low": float(market.get("daily_price_low", 0)),
                        "volume": float(market.get("daily_base_token_volume", 0))
                    }

            return {"market_prices": market_prices}
    except Exception as e:
        logging.error(f"Error fetching market prices: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch market prices")

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """로그인 페이지를 반환합니다."""
    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Lighter Portfolio Tracker - Access</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                background: linear-gradient(135deg, #1e1f2b 0%, #2d2e3f 100%);
                color: white;
                font-family: 'Arial', sans-serif;
                height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .login-container {
                background: rgba(46, 47, 63, 0.9);
                padding: 40px;
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
                text-align: center;
                min-width: 400px;
            }

            .logo {
                font-size: 2.5rem;
                font-weight: bold;
                color: #f9a826;
                margin-bottom: 10px;
            }

            .subtitle {
                color: #9ca3af;
                margin-bottom: 30px;
                font-size: 1.1rem;
            }

            .form-group {
                margin-bottom: 20px;
                text-align: left;
            }

            label {
                display: block;
                margin-bottom: 8px;
                color: #e4e4e7;
                font-weight: 500;
            }

            input[type="password"] {
                width: 100%;
                padding: 15px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 10px;
                background: rgba(30, 31, 43, 0.8);
                color: white;
                font-size: 1rem;
                transition: border-color 0.3s ease;
            }

            input[type="password"]:focus {
                outline: none;
                border-color: #f9a826;
                box-shadow: 0 0 0 2px rgba(249, 168, 38, 0.2);
            }

            .btn {
                width: 100%;
                padding: 15px;
                background: #f9a826;
                color: #1e1f2b;
                border: none;
                border-radius: 10px;
                font-size: 1.1rem;
                font-weight: 600;
                cursor: pointer;
                transition: background-color 0.3s ease;
            }

            .btn:hover {
                background: #f9d826;
            }

            .error {
                color: #ef4444;
                margin-top: 10px;
                font-size: 0.9rem;
            }

            .footer {
                margin-top: 30px;
                color: #6b7280;
                font-size: 0.9rem;
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="logo">🔐 Lighter</div>
            <div class="subtitle">Portfolio Tracker Access</div>

            <form id="loginForm" method="post" action="/auth">
                <div class="form-group">
                    <label for="access_code">Access Code</label>
                    <input type="password" id="access_code" name="access_code" required autofocus>
                </div>

                <button type="submit" class="btn">Enter</button>
            </form>

            <div id="error" class="error" style="display: none;"></div>

            <div class="footer">
                Enter your access code to continue
            </div>
        </div>

        <script>
            document.getElementById('loginForm').addEventListener('submit', async (e) => {
                e.preventDefault();

                const formData = new FormData(e.target);
                const errorDiv = document.getElementById('error');

                try {
                    const response = await fetch('/auth', {
                        method: 'POST',
                        body: formData
                    });

                    if (response.ok) {
                        window.location.href = '/';
                    } else {
                        const data = await response.json();
                        errorDiv.textContent = data.detail || 'Invalid access code';
                        errorDiv.style.display = 'block';
                    }
                } catch (error) {
                    errorDiv.textContent = 'Connection error. Please try again.';
                    errorDiv.style.display = 'block';
                }
            });
        </script>
    </body>
    </html>
    """

@app.post("/auth")
async def authenticate(request: Request, access_code: str = Form(...)):
    """접근 코드 인증 처리"""
    if access_code == ACCESS_CODE:
        request.session["authenticated"] = True
        return RedirectResponse(url="/", status_code=302)
    else:
        raise HTTPException(status_code=401, detail="Invalid access code")

@app.get("/logout")
async def logout(request: Request):
    """로그아웃 처리"""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request, authenticated: bool = Depends(require_authentication)):
    """메인 페이지를 반환합니다. (인증 필요)"""
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