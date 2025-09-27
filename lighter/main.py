from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any
import httpx
import json
import logging
from datetime import datetime
import os

# 로깅 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(current_dir, 'wallet_search_log.txt')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

app = FastAPI(title="Lighter Portfolio Tracker")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 설정
API_BASE_URL = "https://mainnet.zklighter.elliot.ai/api/v1/account"

class WalletRequest(BaseModel):
    addresses: List[str]

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
async def fetch_accounts(wallet_request: WalletRequest, request: Request):
    """여러 지갑 주소의 데이터를 가져옵니다."""
    if len(wallet_request.addresses) > 20:
        raise HTTPException(status_code=400, detail="최대 20개의 주소만 조회할 수 있습니다.")
    
    # 로그 기록
    client_ip = request.client.host
    logging.info(f"IP: {client_ip} | Addresses: {', '.join(wallet_request.addresses)}")
    
    accounts_data = []
    position_summary = {}  # 심볼별 포지션 합계
    
    async with httpx.AsyncClient() as client:
        for address in wallet_request.addresses:
            if not address.strip():
                continue
                
            try:
                response = await client.get(
                    f"{API_BASE_URL}?by=l1_address&value={address.strip()}"
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
                            position_summary[symbol]["accounts"].append(address.strip()[:8] + "...")
                    
                    account["positions"] = filtered_positions
                    accounts_data.append(account)
                    
            except Exception as e:
                logging.error(f"Error fetching data for {address}: {str(e)}")
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