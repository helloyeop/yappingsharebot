# VPS 보안 체크리스트

## 즉시 확인 필요 사항

### 1. Nginx 보안 설정 추가
```bash
# VPS에서 실행
sudo nano /etc/nginx/sites-available/ypab5.com
```

다음 내용 추가:
```nginx
# 민감한 파일 접근 차단
location ~ /\. {
    deny all;
    return 404;
}

location ~ \.(py|db|env|git|md)$ {
    deny all;
    return 404;
}

location ~ /(app|templates|__pycache__|venv)/ {
    deny all;
    return 404;
}

# 보안 헤더 추가
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-XSS-Protection "1; mode=block" always;
```

### 2. API 보안 강화
main.py에서 CORS 설정 수정:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ypab5.com", "https://www.ypab5.com"],  # 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
```

### 3. 방화벽 설정 확인
```bash
# SSH, HTTP, HTTPS만 허용
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# 8000 포트는 외부에서 접근 불가하도록
sudo ufw delete allow 8000/tcp
```

### 4. 파일 권한 확인
```bash
# 민감한 파일 권한 설정
chmod 600 /home/yapper/app/.env
chmod 600 /home/yapper/app/*.db
```

### 5. Fail2ban 설치 (SSH 보안)
```bash
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 6. 정기 보안 업데이트
```bash
# 자동 보안 업데이트 설치
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

## 중장기 보안 개선사항

1. **API 인증 추가**
   - API 키 또는 JWT 토큰 기반 인증
   - Rate limiting 구현

2. **HTTPS 설정** (이미 예정됨)
   - Let's Encrypt SSL 인증서 설치
   - HTTP를 HTTPS로 리다이렉트

3. **로깅 및 모니터링**
   - 접근 로그 모니터링
   - 이상 접근 패턴 감지

4. **백업 전략**
   - 데이터베이스 정기 백업
   - 코드 백업

5. **환경 분리**
   - 개발/운영 환경 분리
   - 운영 환경에서 DEBUG=False 확인

## 텔레그램 봇 보안

1. **Webhook 대신 Polling 사용 중** (현재 안전)
2. **ALLOWED_CHAT_IDS로 접근 제한** (좋음)
3. **봇 토큰 정기 교체 권장**

## 데이터베이스 보안

1. **SQLite 파일 위치** - 웹 루트 밖에 위치 (안전)
2. **SQL Injection 방지** - SQLAlchemy ORM 사용 (안전)
3. **정기 백업 설정 필요**

## 확인 명령어
```bash
# 보안 점검
sudo nginx -t  # Nginx 설정 테스트
sudo ufw status  # 방화벽 상태
ls -la /home/yapper/app/.env  # 파일 권한
curl -I https://ypab5.com/.env  # 민감 파일 접근 테스트
```