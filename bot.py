import os
import logging
import re
from typing import List
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
import httpx
from urllib.parse import urlparse

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")
ALLOWED_CHAT_IDS = os.getenv("ALLOWED_CHAT_IDS", "").split(",") if os.getenv("ALLOWED_CHAT_IDS") else []
ADMIN_USER_IDS = [int(id.strip()) for id in os.getenv("ADMIN_USER_IDS", "").split(",") if id.strip().isdigit()]

# 초기 핵심 태그 목록 (변경 불가)
CORE_TAGS = ["crypto", "eth", "btc", "defi", "nft", "web3", "trading", "market"]

class TwitterBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("share", self.share_tweet))
        self.application.add_handler(CommandHandler("mytweets", self.my_tweets))
        self.application.add_handler(CommandHandler("delete", self.delete_tweet))
        self.application.add_handler(CommandHandler("stats", self.stats))
        self.application.add_handler(CommandHandler("addtag", self.add_tag))
        self.application.add_handler(CommandHandler("removetag", self.remove_tag))
        self.application.add_handler(CommandHandler("tags", self.list_tags))
    
    def is_authorized_chat(self, chat_id: int) -> bool:
        if not ALLOWED_CHAT_IDS:
            return True
        return str(chat_id) in ALLOWED_CHAT_IDS
    
    def is_admin(self, user_id: int) -> bool:
        """사용자가 관리자인지 확인"""
        return user_id in ADMIN_USER_IDS
    
    async def get_allowed_tags(self) -> List[str]:
        """활성 태그 목록을 API에서 가져오기"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{API_BASE_URL}/tags?limit=500")
                if response.status_code == 200:
                    tags = response.json()
                    # is_active가 True인 태그만 반환
                    active_tags = [tag['name'].lower() for tag in tags if tag.get('is_active', True)]
                    logger.info(f"Fetched {len(active_tags)} active tags from API")
                    return active_tags
        except Exception as e:
            logger.error(f"Error fetching tags: {e}")
        
        # API 호출 실패 시 핵심 태그만 반환
        return CORE_TAGS
    
    def extract_twitter_url(self, text: str) -> str:
        twitter_url_pattern = r'https?://(?:twitter\.com|x\.com)/\w+/status/\d+'
        match = re.search(twitter_url_pattern, text)
        return match.group(0) if match else None
    
    def extract_tags(self, text: str) -> List[str]:
        tag_pattern = r'#(\w+)'
        return re.findall(tag_pattern, text)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized_chat(update.effective_chat.id):
            await update.message.reply_text("❌ 이 봇은 허가된 채팅방에서만 사용할 수 있습니다.")
            return
        
        chat = update.effective_chat
        chat_type = "개인 채팅" if chat.type == "private" else f"그룹 채팅 '{chat.title}'"
        
        welcome_message = f"""
🚀 **Twitter Share Bot 활성화됨** ({chat_type})

🔸 **그룹 멤버 모두 사용 가능한 명령어:**
/share <X 링크> <#태그> [코멘트] - 포스팅 공유 (태그 필수!)
/mytweets - 내가 공유한 포스팅 목록  
/delete <ID> - 포스팅 삭제
/stats - 전체 통계 확인
/help - 도움말

📱 **사용 예시:**
/share https://twitter.com/user/status/123 #crypto 좋은 정보!

⚠️ **주의사항:**
- 태그는 최소 1개 이상 필수입니다
- 허용된 태그만 사용 가능합니다 (/help로 확인)

💡 **그룹에서 사용하는 방법:**
- 그룹 채팅에서 바로 `/share` 명령어 입력
- 모든 멤버가 각자 포스팅 공유 가능
- 웹 대시보드에서 그룹의 모든 포스팅 확인 가능
        """
        await update.message.reply_text(welcome_message)
    
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized_chat(update.effective_chat.id):
            return
        
        allowed_tags = await self.get_allowed_tags()
        help_message = f"""
📖 명령어 상세 설명:

🔗 /share <X 링크> <#태그> [코멘트]
   - X 링크를 대시보드에 공유
   - ⚠️ 태그는 최소 1개 이상 필수입니다!
   - 코멘트는 선택사항입니다
   
✅ 사용 가능한 태그 (필수 선택):
   {', '.join([f'#{tag}' for tag in allowed_tags[:20]])}{'...' if len(allowed_tags) > 20 else ''}
   
🏷️ /tags - 전체 태그 목록 보기
➕ /addtag <태그명> - 새 태그 추가 (모든 사용자)
   
📋 /mytweets
   - 본인이 공유한 포스팅 목록 (최근 10개)
   
🗑️ /delete <포스팅ID>
   - 본인이 공유한 포스팅 삭제
   
📊 /stats
   - 전체 통계 정보 확인
   
💡 예시:
   /share https://twitter.com/user/status/123 #crypto
   /share https://x.com/user/status/456 #eth #defi 이더리움 관련 소식
   /addtag layer2
        """
        await update.message.reply_text(help_message)
    
    async def share_tweet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /share 명령어 처리 함수
        
        사용법: /share <X링크> [#태그1] [#태그2] [코멘트]
        예시: /share https://twitter.com/user/status/123 #crypto #news 좋은 정보!
        """
        if not self.is_authorized_chat(update.effective_chat.id):
            await update.message.reply_text("❌ 이 봇은 허가된 채팅방에서만 사용할 수 있습니다.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ 사용법: /share <X 링크> <#태그> [코멘트]\n"
                "⚠️ 태그는 최소 1개 이상 필수입니다!\n"
                "예시: /share https://twitter.com/user/status/123 #crypto 좋은 정보!"
            )
            return
        
        # 명령어 뒤의 모든 텍스트 합치기
        text = " ".join(context.args)
        
        # 1. X URL 추출
        twitter_url = self.extract_twitter_url(text)
        if not twitter_url:
            await update.message.reply_text(
                "❌ 유효한 X 링크를 찾을 수 없습니다.\n"
                "지원하는 형식: https://twitter.com/user/status/123 또는 https://x.com/user/status/123"
            )
            return
        
        # 2. 태그 추출 (#으로 시작하는 단어들)
        tags = self.extract_tags(text)
        
        # 태그가 없으면 오류
        if not tags:
            allowed_tags = await self.get_allowed_tags()
            await update.message.reply_text(
                f"❌ 최소 1개 이상의 태그를 지정해야 합니다.\n"
                f"✅ 사용 가능한 태그: {', '.join([f'#{tag}' for tag in allowed_tags])}\n"
                f"예시: /share https://twitter.com/user/status/123 #crypto 좋은 정보!\n"
                f"💡 새 태그 추가: /addtag 태그명"
            )
            return
        
        # 태그 검증: 허용된 태그만 사용 가능
        allowed_tags = await self.get_allowed_tags()
        logger.info(f"Allowed tags: {allowed_tags}")
        logger.info(f"User provided tags: {tags}")
        
        # 태그를 소문자로 변환하여 비교
        tags_lower = [tag.lower() for tag in tags]
        invalid_tags = [tag for tag in tags_lower if tag not in allowed_tags]
        
        if invalid_tags:
            await update.message.reply_text(
                f"❌ 허용되지 않은 태그가 포함되어 있습니다: {', '.join([f'#{tag}' for tag in invalid_tags])}\n"
                f"✅ 사용 가능한 태그: {', '.join([f'#{tag}' for tag in allowed_tags])}\n"
                f"💡 새 태그 추가: /addtag {invalid_tags[0]}"
            )
            return
        
        # 태그를 소문자로 변환한 값 사용
        tags = tags_lower
        
        # 3. 코멘트 추출 (URL과 태그를 제거한 나머지 텍스트)
        comment = text
        comment = re.sub(r'https?://\S+', '', comment)  # URL 제거
        comment = re.sub(r'#\w+', '', comment)  # 태그 제거
        comment = comment.strip()  # 앞뒤 공백 제거
        
        # 4. 사용자 정보 가져오기
        user = update.effective_user
        display_name = user.full_name or user.first_name or user.username or "Unknown"
        
        # 5. 먼저 사용자를 등록하거나 업데이트
        try:
            async with httpx.AsyncClient() as client:
                user_data = {
                    "telegram_id": user.id,
                    "telegram_username": user.username or "",
                    "display_name": display_name
                }
                
                # 사용자 생성/업데이트 API 호출
                user_response = await client.post(f"{API_BASE_URL}/users", json=user_data)
                
                if user_response.status_code not in [200, 201]:
                    logger.error(f"User creation failed: {user_response.text}")
        
        except Exception as e:
            logger.error(f"Error creating/updating user: {e}")
        
        # 6. 포스팅 데이터 준비
        tweet_data = {
            "user_id": user.id,
            "tweet_url": twitter_url,
            "tags": tags,
            "comment": comment if comment else None
        }
        
        # 7. 포스팅 등록 API 호출
        logger.info(f"Attempting to register tweet for user {user.id}: {twitter_url}")
        logger.info(f"Tweet data: {tweet_data}")
        logger.info(f"API URL: {API_BASE_URL}/tweets")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{API_BASE_URL}/tweets", json=tweet_data)
                
                logger.info(f"API Response Status: {response.status_code}")
                logger.info(f"API Response Text: {response.text}")
                
                if response.status_code == 200:
                    # 성공 메시지 생성
                    success_msg = "✅ 포스팅이 성공적으로 등록되었습니다!"
                    if tags:
                        success_msg += f"\n🏷️ 태그: {', '.join([f'#{tag}' for tag in tags])}"
                    if comment:
                        success_msg += f"\n💬 코멘트: {comment}"
                    
                    await update.message.reply_text(success_msg)
                
                elif response.status_code == 400:
                    # 클라이언트 오류 (잘못된 URL, 중복 등)
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("detail", "알 수 없는 오류가 발생했습니다.")
                    except:
                        error_msg = f"API 오류: {response.text}"
                    await update.message.reply_text(f"❌ {error_msg}")
                
                elif response.status_code == 404:
                    await update.message.reply_text("❌ 사용자를 찾을 수 없습니다. 먼저 봇을 사용해서 등록해주세요.")
                
                else:
                    # 서버 오류
                    await update.message.reply_text(f"❌ 서버 오류가 발생했습니다 (코드: {response.status_code}). 잠시 후 다시 시도해주세요.")
                    logger.error(f"API Error: {response.status_code} - {response.text}")
        
        except httpx.TimeoutException:
            logger.error("Timeout error when connecting to API")
            await update.message.reply_text("❌ 요청 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.")
            
        except httpx.ConnectError as e:
            logger.error(f"Connection error: {e}")
            await update.message.reply_text(f"❌ 서버에 연결할 수 없습니다. API 서버가 실행 중인지 확인해주세요.\n🔗 {API_BASE_URL}")
            
        except Exception as e:
            logger.error(f"Unexpected error sharing tweet: {e}", exc_info=True)
            await update.message.reply_text(f"❌ 예상치 못한 오류가 발생했습니다: {str(e)}")
    
    async def my_tweets(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /mytweets 명령어 처리 - 사용자가 공유한 포스팅 목록 표시
        """
        if not self.is_authorized_chat(update.effective_chat.id):
            return
        
        user_id = update.effective_user.id
        
        # 페이지 번호 처리 (옵션)
        page = 1
        if context.args and context.args[0].isdigit():
            page = int(context.args[0])
        
        limit = 5  # 텔레그램 메시지에 적합한 개수
        skip = (page - 1) * limit
        
        logger.info(f"Fetching tweets for user {user_id}, page {page}")
        api_url = f"{API_BASE_URL}/users/{user_id}/tweets"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 사용자의 포스팅 목록 조회
                response = await client.get(
                    api_url,
                    params={"skip": skip, "limit": limit}
                )
                
                logger.info(f"MyTweets API Response Status: {response.status_code}")
                logger.info(f"MyTweets API Response Text: {response.text[:500]}...")  # 처음 500자만
                
                if response.status_code == 200:
                    data = response.json()
                    tweets = data.get("tweets", [])
                    total = data.get("total", 0)
                    
                    if not tweets:
                        await update.message.reply_text(
                            "📭 아직 공유한 포스팅이 없습니다.\n"
                            "/share 명령어로 첫 포스팅을 공유해보세요!"
                        )
                        return
                    
                    # 메시지 생성 (HTML 형식으로 안전하게)
                    def escape_html(text):
                        """HTML 특수문자를 이스케이프합니다."""
                        if not text:
                            return ""
                        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    
                    message = f"📋 <b>내가 공유한 포스팅</b> (총 {total}개)\n"
                    message += f"📄 페이지 {page}/{(total + limit - 1) // limit}\n\n"
                    
                    for i, tweet in enumerate(tweets, 1):
                        tweet_num = skip + i
                        tweet_id = tweet.get("id", "")
                        tweet_url = tweet.get("tweet_url", "")
                        comment = tweet.get("comment", "")
                        tags = tweet.get("tags", [])
                        created_at = tweet.get("created_at", "")
                        
                        # 날짜 포맷팅
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            date_str = dt.strftime("%Y-%m-%d %H:%M")
                        except:
                            date_str = created_at[:10] if created_at else ""
                        
                        message += f"<b>{tweet_num}.</b> "
                        
                        # 태그 표시
                        if tags:
                            tag_names = [f"#{escape_html(tag['name'])}" for tag in tags]
                            message += f"{' '.join(tag_names)} "
                        
                        # 코멘트 표시
                        if comment:
                            display_comment = escape_html(comment[:50])
                            if len(comment) > 50:
                                display_comment += "..."
                            message += f"\n💬 {display_comment}"
                        
                        message += f"\n🔗 <a href='{tweet_url}'>포스팅 보기</a>"
                        message += f"\n📅 {escape_html(date_str)}"
                        
                        # UUID를 짧게 표시 (처음 8자만)
                        short_id = tweet_id[:8] if tweet_id else ""
                        message += f"\n🗑 삭제: <code>/delete {short_id}</code>\n\n"
                    
                    # 페이지 네비게이션
                    if total > limit:
                        message += "📍 다른 페이지 보기: "
                        if page > 1:
                            message += f"<code>/mytweets {page-1}</code> ◀️ "
                        if page < (total + limit - 1) // limit:
                            message += f"▶️ <code>/mytweets {page+1}</code>"
                    
                    await update.message.reply_text(
                        message,
                        parse_mode="HTML",
                        disable_web_page_preview=True  # URL 미리보기 비활성화
                    )
                    
                elif response.status_code == 404:
                    # 사용자가 등록되지 않은 경우
                    await update.message.reply_text(
                        "❌ 먼저 포스팅을 공유해야 합니다.\n"
                        "/share 명령어를 사용해보세요!"
                    )
                else:
                    await update.message.reply_text("❌ 포스팅 목록을 가져올 수 없습니다.")
        
        except httpx.TimeoutException:
            logger.error("Timeout error when fetching user tweets")
            await update.message.reply_text("❌ 요청 시간이 초과되었습니다.")
        except httpx.ConnectError as e:
            logger.error(f"Connection error when fetching tweets: {e}")
            await update.message.reply_text(f"❌ 서버에 연결할 수 없습니다. API 서버가 실행 중인지 확인해주세요.\n🔗 {api_url}")
        except Exception as e:
            logger.error(f"Error fetching user tweets: {e}", exc_info=True)
            await update.message.reply_text(f"❌ 서버 연결 오류가 발생했습니다: {str(e)}")
    
    async def delete_tweet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /delete 명령어 처리 - 포스팅 삭제
        사용법: /delete <짧은ID>
        """
        if not self.is_authorized_chat(update.effective_chat.id):
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ 사용법: /delete <짧은ID>\n"
                "💡 /mytweets 명령어로 삭제할 포스팅의 짧은 ID를 확인하세요."
            )
            return
        
        short_id = context.args[0]
        user_id = update.effective_user.id
        
        logger.info(f"Attempting to delete tweet with short ID: {short_id} for user: {user_id}")
        
        try:
            # 먼저 사용자의 모든 포스팅을 가져와서 짧은 ID로 매칭
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{API_BASE_URL}/users/{user_id}/tweets?limit=100")
                
                if response.status_code != 200:
                    await update.message.reply_text("❌ 포스팅 목록을 가져올 수 없습니다.")
                    return
                
                data = response.json()
                tweets = data.get("tweets", [])
                
                # 짧은 ID로 포스팅 찾기
                target_tweet = None
                for tweet in tweets:
                    tweet_full_id = tweet.get("id", "")
                    if tweet_full_id.startswith(short_id):
                        target_tweet = tweet
                        break
                
                if not target_tweet:
                    await update.message.reply_text(
                        f"❌ 짧은 ID '{short_id}'에 해당하는 포스팅을 찾을 수 없습니다.\n"
                        "💡 /mytweets 명령어로 올바른 ID를 확인하세요."
                    )
                    return
                
                # 포스팅 삭제 API 호출
                full_tweet_id = target_tweet.get("id")
                delete_response = await client.delete(
                    f"{API_BASE_URL}/tweets/{full_tweet_id}",
                    params={"user_id": user_id}
                )
                
                logger.info(f"Delete response: {delete_response.status_code} - {delete_response.text}")
                
                if delete_response.status_code == 200:
                    tweet_url = target_tweet.get("tweet_url", "")
                    await update.message.reply_text(
                        f"✅ 포스팅이 성공적으로 삭제되었습니다!\n"
                        f"🔗 {tweet_url}"
                    )
                elif delete_response.status_code == 403:
                    await update.message.reply_text("❌ 본인이 작성한 포스팅만 삭제할 수 있습니다.")
                elif delete_response.status_code == 404:
                    await update.message.reply_text("❌ 포스팅을 찾을 수 없습니다.")
                else:
                    await update.message.reply_text(f"❌ 삭제 실패 (코드: {delete_response.status_code})")
                    
        except Exception as e:
            logger.error(f"Error deleting tweet: {e}", exc_info=True)
            await update.message.reply_text(f"❌ 삭제 중 오류가 발생했습니다: {str(e)}")
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized_chat(update.effective_chat.id):
            return
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{API_BASE_URL}/stats")
                
                if response.status_code == 200:
                    await update.message.reply_text("📊 통계 조회 기능 구현 예정")
                else:
                    await update.message.reply_text("❌ 통계를 가져올 수 없습니다.")
        
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            await update.message.reply_text("❌ 서버 연결 오류가 발생했습니다.")
    
    async def add_tag(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /addtag 명령어 - 새 태그 추가 (모든 사용자)
        """
        if not self.is_authorized_chat(update.effective_chat.id):
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ 사용법: /addtag <태그명>\n"
                "예시: /addtag layer2\n"
                "💡 태그명은 영문, 숫자만 가능합니다."
            )
            return
        
        tag_name = context.args[0].lower().strip()
        
        # 태그명 검증 (영문, 숫자만)
        if not re.match(r'^[a-zA-Z0-9]+$', tag_name):
            await update.message.reply_text(
                "❌ 태그명은 영문과 숫자만 사용 가능합니다.\n"
                "예시: layer2, web3, defi2024"
            )
            return
        
        # 태그 길이 제한
        if len(tag_name) > 20:
            await update.message.reply_text("❌ 태그명은 20자 이내로 입력해주세요.")
            return
        
        user = update.effective_user
        
        try:
            # 먼저 사용자 등록/업데이트
            async with httpx.AsyncClient() as client:
                user_data = {
                    "telegram_id": user.id,
                    "telegram_username": user.username or "",
                    "display_name": user.full_name or user.first_name or user.username or "Unknown"
                }
                await client.post(f"{API_BASE_URL}/users", json=user_data)
                
                # 태그 생성
                tag_data = {
                    "name": tag_name,
                    "created_by": user.id
                }
                
                response = await client.post(f"{API_BASE_URL}/tags", json=tag_data)
                
                if response.status_code == 200:
                    await update.message.reply_text(
                        f"✅ 새 태그 '#{tag_name}'이(가) 추가되었습니다!\n"
                        f"이제 /share 명령어에서 사용할 수 있습니다."
                    )
                elif response.status_code == 400:
                    error_data = response.json()
                    error_msg = error_data.get("detail", "태그 추가 실패")
                    await update.message.reply_text(f"❌ {error_msg}")
                else:
                    await update.message.reply_text("❌ 태그 추가에 실패했습니다.")
                    
        except Exception as e:
            logger.error(f"Error adding tag: {e}")
            await update.message.reply_text("❌ 서버 오류가 발생했습니다.")
    
    async def remove_tag(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /removetag 명령어 - 태그 비활성화 (관리자만)
        """
        if not self.is_authorized_chat(update.effective_chat.id):
            return
        
        user_id = update.effective_user.id
        
        # 관리자 권한 확인
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ 이 명령어는 관리자만 사용할 수 있습니다.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ 사용법: /removetag <태그명>\n"
                "예시: /removetag spam"
            )
            return
        
        tag_name = context.args[0].lower().strip().replace('#', '')
        
        # 핵심 태그는 삭제 불가
        if tag_name in CORE_TAGS:
            await update.message.reply_text(
                f"❌ '#{tag_name}'은(는) 핵심 태그로 삭제할 수 없습니다.\n"
                f"핵심 태그: {', '.join([f'#{tag}' for tag in CORE_TAGS])}"
            )
            return
        
        try:
            async with httpx.AsyncClient() as client:
                # 태그 비활성화 API 호출
                response = await client.delete(f"{API_BASE_URL}/tags/{tag_name}")
                
                if response.status_code == 200:
                    await update.message.reply_text(
                        f"✅ 태그 '#{tag_name}'이(가) 비활성화되었습니다.\n"
                        f"더 이상 /share 명령어에서 사용할 수 없습니다."
                    )
                elif response.status_code == 404:
                    await update.message.reply_text(f"❌ 태그 '#{tag_name}'을(를) 찾을 수 없습니다.")
                else:
                    await update.message.reply_text("❌ 태그 비활성화에 실패했습니다.")
                    
        except Exception as e:
            logger.error(f"Error removing tag: {e}")
            await update.message.reply_text("❌ 서버 오류가 발생했습니다.")
    
    async def list_tags(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /tags 명령어 - 전체 활성 태그 목록
        """
        if not self.is_authorized_chat(update.effective_chat.id):
            return
        
        try:
            allowed_tags = await self.get_allowed_tags()
            
            # 핵심 태그와 사용자 추가 태그 구분
            core_tags = [tag for tag in allowed_tags if tag in CORE_TAGS]
            user_tags = [tag for tag in allowed_tags if tag not in CORE_TAGS]
            
            message = "🏷️ **사용 가능한 태그 목록**\n\n"
            
            if core_tags:
                message += "**📌 핵심 태그:**\n"
                message += f"{', '.join([f'#{tag}' for tag in sorted(core_tags)])}\n\n"
            
            if user_tags:
                message += "**➕ 사용자 추가 태그:**\n"
                message += f"{', '.join([f'#{tag}' for tag in sorted(user_tags)])}\n\n"
            
            message += f"📊 전체 태그 수: {len(allowed_tags)}개\n"
            message += "\n💡 새 태그 추가: /addtag <태그명>"
            
            if self.is_admin(update.effective_user.id):
                message += "\n🔧 태그 삭제: /removetag <태그명> (관리자)"
            
            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Error listing tags: {e}")
            await update.message.reply_text("❌ 태그 목록을 가져올 수 없습니다.")
    
    def run(self):
        self.application.run_polling()

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is required!")
        exit(1)
    
    bot = TwitterBot()
    logger.info("Starting Twitter Share Bot...")
    bot.run()