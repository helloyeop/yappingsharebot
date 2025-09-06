# 🚀 Yapper Dash 배포 가이드

## 📊 배포 옵션 비교

### 🆓 **무료 배포 옵션** (SQLite 사용 추천)

#### 1. **Render.com** ⭐️ 추천!
- **장점**: 
  - 완전 무료 플랜 제공
  - SQLite 지원
  - 자동 HTTPS
  - GitHub 연동으로 자동 배포
- **단점**: 
  - 무료 플랜은 15분 미활동시 슬립 (첫 요청시 30초 대기)
- **설정 방법**:
  ```yaml
  # render.yaml
  services:
    - type: web
      name: yapper-dash
      env: python
      buildCommand: "pip install -r requirements.txt"
      startCommand: "python main.py"
      envVars:
        - key: DATABASE_URL
          value: sqlite:///./yapper_dash.db
  ```

#### 2. **Railway** 
- **장점**: 
  - $5 무료 크레딧
  - SQLite 지원
  - 간단한 배포
- **단점**: 
  - 크레딧 소진 후 유료
- **설정**: GitHub 연결 후 자동 감지

#### 3. **PythonAnywhere**
- **장점**: 
  - 완전 무료
  - SQLite 기본 지원
- **단점**: 
  - 텔레그램 봇 실행 제한 (스케줄러로 해결 가능)
  - 느린 무료 플랜

#### 4. **Vercel** (API만)
- **장점**: 
  - 완전 무료
  - 빠른 속도
- **단점**: 
  - SQLite 파일 저장 불가 (읽기 전용)
  - API 전용

### 💰 **유료 배포 옵션** (PostgreSQL 가능)

#### 1. **Heroku** ($5~/월)
- PostgreSQL 무료 애드온
- 안정적인 성능

#### 2. **AWS/GCP/Azure** 
- 프리티어 1년
- 복잡한 설정

## 🎯 **초보자를 위한 추천 조합**

### **옵션 1: 가장 간단한 방법** ✅
```
- 웹서버: Render.com (무료)
- 데이터베이스: SQLite (내장)
- 텔레그램 봇: 로컬 PC에서 실행
```

### **옵션 2: 완전 클라우드** 
```
- 웹서버: Railway ($5 크레딧)
- 데이터베이스: SQLite
- 텔레그램 봇: Railway 백그라운드 워커
```

## 📝 **Render.com 배포 단계별 가이드**

### 1. GitHub에 코드 업로드
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/yapper-dash.git
git push -u origin main
```

### 2. Render.com 설정
1. [render.com](https://render.com) 가입
2. "New +" → "Web Service" 클릭
3. GitHub 연결 및 레포지토리 선택
4. 설정:
   - **Name**: yapper-dash
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py`
5. 환경변수 추가:
   - `TELEGRAM_BOT_TOKEN`: 봇 토큰
   - `ALLOWED_CHAT_IDS`: 허용된 채팅방 ID

### 3. 배포 확인
- 배포 완료 후 제공된 URL 접속
- 예: `https://yapper-dash.onrender.com`

## 🔧 **배포 전 체크리스트**

### 1. `.gitignore` 파일 생성
```gitignore
# 환경 파일
.env
*.db
*.sqlite

# Python
__pycache__/
*.py[cod]
*$py.class
.Python
.conda/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

### 2. 프로덕션 설정
```python
# config.py 수정
class Settings(BaseSettings):
    # 프로덕션에서는 환경변수 사용
    database_url: str = Field(default="sqlite:///./yapper_dash.db")
    debug: bool = Field(default=False)
    
    class Config:
        env_file = ".env"
```

### 3. 보안 설정
- `ALLOWED_CHAT_IDS` 환경변수 설정 필수
- 봇 토큰 절대 코드에 하드코딩 금지

## 💡 **배포 팁**

### SQLite 백업
```python
# 자동 백업 스크립트
import shutil
from datetime import datetime

def backup_database():
    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy('yapper_dash.db', backup_name)
```

### 모니터링
- Render.com 대시보드에서 로그 확인
- `/health` 엔드포인트로 상태 체크

### 텔레그램 봇 24시간 실행
1. **로컬**: 항상 켜진 PC/라즈베리파이
2. **클라우드**: Railway 워커 또는 VPS
3. **하이브리드**: 웹은 클라우드, 봇은 로컬

## 🆘 **문제 해결**

### "Application failed to respond"
- 포트 설정 확인: `PORT` 환경변수 사용
```python
port = int(os.getenv("PORT", 8000))
uvicorn.run(app, host="0.0.0.0", port=port)
```

### SQLite 파일이 사라짐
- Render 무료 플랜은 재배포시 파일 초기화
- 해결: 정기적 백업 또는 유료 플랜 사용

### 봇이 응답하지 않음
- 웹서버와 봇 서버의 API_BASE_URL 확인
- CORS 설정 확인

## 🎉 **결론**

초보자라면:
1. **SQLite + Render.com** 조합 추천
2. 일단 무료로 시작해보세요
3. 사용자가 늘어나면 그때 업그레이드

질문이 있으시면 언제든 물어보세요! 🚀