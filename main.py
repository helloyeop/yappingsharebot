from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from app.db.database import create_tables
from app.routers import tweets, users, tags, stats
import uvicorn
import sys
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작시 실행
    try:
        create_tables()
        print("✅ 데이터베이스 테이블 초기화 완료")
    except Exception as e:
        print(f"⚠️ 데이터베이스 초기화 중 오류: {e}")
        print("💡 데이터베이스 연결을 확인하고 init_db.py를 실행해보세요.")
    
    yield
    
    # 종료시 실행 (필요시 정리 작업)
    print("🛑 서버 종료")

app = FastAPI(
    title="웹3 생존기 infoFi",
    description="텔레그램 봇을 통한 web3 포스팅 공유 대시보드",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Lighter 앱 설정
sys.path.insert(0, os.path.dirname(__file__))
from lighter.main import app as lighter_app
app.mount("/lighter/static", StaticFiles(directory="lighter/static"), name="lighter_static")
app.mount("/lighter", lighter_app)

app.include_router(tweets.router, prefix="/api", tags=["tweets"])
app.include_router(users.router, prefix="/api", tags=["users"])
app.include_router(tags.router, prefix="/api", tags=["tags"])
app.include_router(stats.router, prefix="/api", tags=["stats"])

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/yapper")
async def yapper_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)