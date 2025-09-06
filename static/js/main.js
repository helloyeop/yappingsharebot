/**
 * Yapper Dash - Twitter Share Dashboard JavaScript
 * API 연동 및 동적 UI 구현
 */

class Dashboard {
    constructor() {
        this.apiBaseUrl = '/api';
        this.currentPage = 1;
        this.tweetsPerPage = 12;
        this.filters = {
            search: '',
            user_id: null,
            username: '',
            tag: '',
            tags: [],
            date_from: '',
            date_to: '',
            sort_by: 'newest'
        };
        
        // 허용된 태그 목록 (API에서 동적으로 로드)
        this.allowedTags = [];
        
        // 현재 로드된 포스팅 데이터 (모달 네비게이션용)
        this.currentTweetsData = [];
        this.currentModalTweetIndex = -1;
        
        this.init();
    }

    async init() {
        console.log('🚀 Yapper Dash Dashboard 초기화 중... v2');
        
        // DOM 요소 캐싱
        this.cacheElements();
        console.log('📦 DOM 요소 캐싱 완료');
        
        // 이벤트 리스너 설정
        this.setupEventListeners();
        console.log('🎧 이벤트 리스너 설정 완료');
        
        // 초기 데이터 로드
        console.log('📡 초기 데이터 로드 시작...');
        await this.loadInitialData();
        
        console.log('✅ Dashboard 초기화 완료');
    }

    cacheElements() {
        // 통계 요소
        this.statsElements = {
            totalTweets: document.getElementById('total-tweets'),
            totalUsers: document.getElementById('total-users'),
            totalTags: document.getElementById('total-tags'),
            tweetsToday: document.getElementById('tweets-today')
        };

        // 필터 요소
        this.filterElements = {
            toggle: document.getElementById('filter-toggle'),
            content: document.getElementById('filters-content'),
            search: document.getElementById('search-input'),
            searchBtn: document.getElementById('search-btn'),
            userSelect: document.getElementById('user-select'),
            tagSelect: document.getElementById('tag-select'),
            dateRange: document.getElementById('date-range'),
            dateFrom: document.getElementById('date-from'),
            dateTo: document.getElementById('date-to'),
            sortSelect: document.getElementById('sort-select'),
            resetBtn: document.getElementById('reset-filters')
        };

        // 콘텐츠 요소
        this.contentElements = {
            popularTags: document.getElementById('popular-tags'),
            tweetsGrid: document.getElementById('tweets-grid'),
            loadingContainer: document.getElementById('loading-container'),
            emptyState: document.getElementById('empty-state'),
            paginationContainer: document.getElementById('pagination-container'),
            tweetsPerPageSelect: document.getElementById('tweets-per-page')
        };

        // 도움말 요소
        this.helpElements = {
            toggle: document.getElementById('help-toggle'),
            content: document.getElementById('help-content')
        };

        // 모달 요소
        this.modalElements = {
            modal: document.getElementById('tweet-modal'),
            backdrop: document.querySelector('.tweet-modal-backdrop'),
            closeBtn: document.getElementById('close-modal-btn'),
            prevBtn: document.getElementById('prev-tweet-btn'),
            nextBtn: document.getElementById('next-tweet-btn'),
            userAvatar: document.getElementById('modal-user-avatar'),
            userName: document.getElementById('modal-user-name'),
            tweetDate: document.getElementById('modal-tweet-date'),
            tweetComment: document.getElementById('modal-tweet-comment'),
            tweetTags: document.getElementById('modal-tweet-tags'),
            tweetLink: document.getElementById('modal-tweet-link'),
            embedContainer: document.getElementById('modal-tweet-embed')
        };
    }

    setupEventListeners() {
        // 도움말 토글
        if (this.helpElements.toggle) {
            this.helpElements.toggle.addEventListener('click', this.toggleHelp.bind(this));
        }

        // 필터 토글
        if (this.filterElements.toggle) {
            this.filterElements.toggle.addEventListener('click', this.toggleFilters.bind(this));
        }

        // 검색
        if (this.filterElements.search) {
            this.filterElements.search.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.handleSearch();
                }
            });
        }
        
        if (this.filterElements.searchBtn) {
            this.filterElements.searchBtn.addEventListener('click', this.handleSearch.bind(this));
        }

        // 필터 변경
        const filterInputs = [
            'userSelect', 'tagSelect', 'dateFrom', 'dateTo', 'sortSelect'
        ];
        
        filterInputs.forEach(inputName => {
            const element = this.filterElements[inputName];
            if (element) {
                element.addEventListener('change', this.handleFilterChange.bind(this));
            }
        });

        // 날짜 범위 선택 이벤트
        if (this.filterElements.dateRange) {
            this.filterElements.dateRange.addEventListener('change', this.handleDateRangeChange.bind(this));
        }

        // 초기화 버튼
        if (this.filterElements.resetBtn) {
            this.filterElements.resetBtn.addEventListener('click', this.resetFilters.bind(this));
        }

        // 포스팅 수 변경
        if (this.contentElements.tweetsPerPageSelect) {
            this.contentElements.tweetsPerPageSelect.addEventListener('change', (e) => {
                this.tweetsPerPage = parseInt(e.target.value);
                this.currentPage = 1;
                this.loadTweets();
            });
        }

        // 모달 이벤트 리스너 설정
        this.setupModalEventListeners();
    }

    async loadInitialData() {
        try {
            // 병렬로 데이터 로드
            await Promise.all([
                this.loadStats(),
                this.loadUsers(),
                this.loadTags(),
                this.loadAllowedTags(),  // loadPopularTags 대신 loadAllowedTags 사용
                this.loadTweets()
            ]);
        } catch (error) {
            console.error('초기 데이터 로드 실패:', error);
            this.showError('데이터를 로드할 수 없습니다.');
        }
    }

    async loadStats() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/stats`);
            if (!response.ok) throw new Error('통계 로드 실패');
            
            const stats = await response.json();
            this.updateStats(stats);
        } catch (error) {
            console.error('통계 로드 오류:', error);
            this.updateStats({ total_tweets: '-', total_users: '-', total_tags: '-', tweets_today: '-' });
        }
    }

    updateStats(stats) {
        if (this.statsElements.totalTweets) {
            this.statsElements.totalTweets.textContent = stats.total_tweets || 0;
        }
        if (this.statsElements.totalUsers) {
            this.statsElements.totalUsers.textContent = stats.total_users || 0;
        }
        if (this.statsElements.totalTags) {
            this.statsElements.totalTags.textContent = stats.total_tags || 0;
        }
        if (this.statsElements.tweetsToday) {
            this.statsElements.tweetsToday.textContent = stats.tweets_today || 0;
        }
    }

    async loadUsers() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/users`);
            if (!response.ok) throw new Error('사용자 로드 실패');
            
            const users = await response.json();
            this.populateUserSelect(users);
        } catch (error) {
            console.error('사용자 로드 오류:', error);
        }
    }

    populateUserSelect(users) {
        if (!this.filterElements.userSelect) return;
        
        // 기존 옵션 제거 (첫 번째 제외)
        while (this.filterElements.userSelect.children.length > 1) {
            this.filterElements.userSelect.removeChild(this.filterElements.userSelect.lastChild);
        }

        // 사용자 옵션 추가
        users.forEach(user => {
            const option = document.createElement('option');
            option.value = user.telegram_id;
            option.textContent = user.display_name || user.telegram_username;
            this.filterElements.userSelect.appendChild(option);
        });
    }

    async loadTags() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/tags`);
            if (!response.ok) throw new Error('태그 로드 실패');
            
            const tags = await response.json();
            this.populateTagSelect(tags);
        } catch (error) {
            console.error('태그 로드 오류:', error);
        }
    }

    populateTagSelect(tags) {
        if (!this.filterElements.tagSelect) return;
        
        // 기존 옵션 제거 (첫 번째 제외)
        while (this.filterElements.tagSelect.children.length > 1) {
            this.filterElements.tagSelect.removeChild(this.filterElements.tagSelect.lastChild);
        }

        // 활성 태그만 필터링 (안전장치)
        const activeTags = tags.filter(tag => tag.is_active !== false && tag.is_active !== 0);
        
        // 핵심 태그와 사용자 태그 분리하여 정렬
        const coreTags = activeTags.filter(tag => tag.is_core);
        const userTags = activeTags.filter(tag => !tag.is_core);
        
        // 태그 옵션 추가 (핵심 태그 먼저, 그 다음 사용자 태그)
        [...coreTags, ...userTags].forEach(tag => {
            const option = document.createElement('option');
            option.value = tag.name;
            option.textContent = `#${tag.name}${tag.is_core ? ' ⭐' : ''}`;
            this.filterElements.tagSelect.appendChild(option);
        });
    }

    async loadAllowedTags() {
        try {
            console.log('📋 태그 로드 시작...');
            // API에서 모든 활성 태그 가져오기
            const response = await fetch(`${this.apiBaseUrl}/tags?limit=500`);
            console.log('📋 태그 API 응답:', response.status);
            
            if (response.ok) {
                const tags = await response.json();
                console.log('📋 받은 태그 개수:', tags.length);
                
                // 활성 태그만 필터링 (안전장치: is_active가 없으면 true로 간주)
                const activeTags = tags.filter(tag => tag.is_active !== false && tag.is_active !== 0);
                console.log('📋 활성 태그 개수:', activeTags.length);
                
                // allowedTags 업데이트
                this.allowedTags = activeTags.map(tag => tag.name.toLowerCase());
                
                // 태그 정보 생성 (사용 횟수 포함)
                const tagsToShow = activeTags.map(tag => ({
                    name: tag.name,
                    count: tag.tweet_count || 0,
                    is_core: tag.is_core || false
                }));
                
                this.renderAllowedTags(tagsToShow);
            } else {
                throw new Error(`태그 로드 실패: ${response.status}`);
            }
        } catch (error) {
            console.error('태그 로드 오류:', error);
            console.error('에러 상세:', error.message, error.stack);
            this.renderPopularTagsError();
        }
    }

    renderAllowedTags(tags) {
        if (!this.contentElements.popularTags) return;
        
        if (!tags || tags.length === 0) {
            this.contentElements.popularTags.innerHTML = '<p class="text-secondary">태그를 로드할 수 없습니다.</p>';
            return;
        }

        // 핵심 태그와 사용자 태그 분리
        const coreTags = tags.filter(tag => tag.is_core);
        const userTags = tags.filter(tag => !tag.is_core);
        
        // 각각 사용 빈도에 따라 정렬
        coreTags.sort((a, b) => b.count - a.count);
        userTags.sort((a, b) => b.count - a.count);
        
        // 핵심 태그를 먼저, 그 다음 사용자 태그
        const sortedTags = [...coreTags, ...userTags];

        const tagsHtml = sortedTags.map(tag => {
            const isActive = tag.count > 0;
            const tagClass = isActive ? 'tag-item' : 'tag-item tag-inactive';
            const coreIndicator = tag.is_core ? ' <i class="fas fa-star" style="font-size: 0.7rem; color: var(--warning-color);"></i>' : '';
            return `
                <a href="#" class="${tagClass}" data-tag="${tag.name}">
                    #${tag.name}${coreIndicator}
                    <span class="tag-count">${tag.count}</span>
                </a>
            `;
        }).join('');

        this.contentElements.popularTags.innerHTML = tagsHtml;

        // 태그 클릭 이벤트
        this.contentElements.popularTags.addEventListener('click', (e) => {
            e.preventDefault();
            const tagElement = e.target.closest('.tag-item');
            if (tagElement && !tagElement.classList.contains('tag-inactive')) {
                const tagName = tagElement.getAttribute('data-tag');
                this.filterByTag(tagName);
            }
        });
    }

    renderPopularTags(tags) {
        // 기존 함수는 남겨두되 renderAllowedTags를 호출
        this.renderAllowedTags(tags);
    }

    renderPopularTagsError() {
        if (this.contentElements.popularTags) {
            this.contentElements.popularTags.innerHTML = '<p class="text-secondary">태그를 로드할 수 없습니다.</p>';
        }
    }

    async loadTweets() {
        try {
            this.showLoading();
            
            const params = this.buildApiParams();
            const response = await fetch(`${this.apiBaseUrl}/tweets?${params}`);
            
            if (!response.ok) throw new Error('포스팅 로드 실패');
            
            const data = await response.json();
            this.renderTweets(data);
            this.renderPagination(data);
            
        } catch (error) {
            console.error('포스팅 로드 오류:', error);
            this.showError('포스팅을 로드할 수 없습니다.');
        } finally {
            this.hideLoading();
        }
    }

    buildApiParams() {
        const params = new URLSearchParams();
        
        // 페이징
        params.append('skip', ((this.currentPage - 1) * this.tweetsPerPage).toString());
        params.append('limit', this.tweetsPerPage.toString());
        
        // 필터
        if (this.filters.search) params.append('search', this.filters.search);
        if (this.filters.user_id) params.append('user_id', this.filters.user_id);
        if (this.filters.username) params.append('username', this.filters.username);
        if (this.filters.tag) params.append('tag', this.filters.tag);
        if (this.filters.date_from) params.append('date_from', this.filters.date_from);
        if (this.filters.date_to) params.append('date_to', this.filters.date_to);
        if (this.filters.sort_by) params.append('sort_by', this.filters.sort_by);
        
        return params.toString();
    }

    renderTweets(data) {
        console.log('🎨 포스팅 렌더링 시작:', data.tweets ? data.tweets.length : 0, '개');
        
        if (!this.contentElements.tweetsGrid) {
            console.error('❌ tweetsGrid 요소를 찾을 수 없음');
            return;
        }
        
        if (!data.tweets || data.tweets.length === 0) {
            console.log('📭 포스팅이 없음, 빈 상태 표시');
            this.showEmpty();
            return;
        }

        // 현재 포스팅 데이터 저장 (모달 네비게이션용)
        this.currentTweetsData = data.tweets;

        const tweetsHtml = data.tweets.map(tweet => this.createTweetCard(tweet)).join('');
        console.log('🔧 생성된 HTML 길이:', tweetsHtml.length);
        
        this.contentElements.tweetsGrid.innerHTML = tweetsHtml;
        console.log('✅ 포스팅 렌더링 완료');
        
        // 포스팅 미리보기 버튼 이벤트 리스너 추가
        this.setupTweetPreviewListeners();
        
        this.hideEmpty();
    }

    createTweetCard(tweet) {
        const userInitial = (tweet.user?.display_name || tweet.user?.telegram_username || '?')[0].toUpperCase();
        const userName = tweet.user?.display_name || tweet.user?.telegram_username || 'Unknown';
        const tweetDate = this.formatDate(tweet.created_at);
        const comment = tweet.comment || '';
        const tags = tweet.tags || [];
        
        const tagsHtml = tags.map(tag => 
            `<a href="#" class="tweet-tag" data-tag="${tag.name}">#${tag.name}</a>`
        ).join('');

        // 포스팅 ID 추출 (URL에서)
        const tweetId = this.extractTweetId(tweet.tweet_url);
        const embedId = `tweet-embed-${tweetId}`;

        return `
            <article class="tweet-card" data-tweet-id="${tweetId}">
                <header class="tweet-header">
                    <div class="user-avatar">${userInitial}</div>
                    <div class="user-info">
                        <div class="user-name">${this.escapeHtml(userName)}</div>
                        <div class="tweet-date">${tweetDate}</div>
                    </div>
                </header>
                
                <div class="tweet-content">
                    ${comment ? `<p class="tweet-comment">${this.escapeHtml(comment)}</p>` : ''}
                    
                    ${tags.length > 0 ? `<div class="tweet-tags">${tagsHtml}</div>` : ''}
                    
                    <!-- 포스팅 미리보기 영역 -->
                    <div class="tweet-preview-actions">
                        <button type="button" class="btn-modal-preview" data-tweet-id="${tweetId}">
                            <i class="fas fa-eye"></i> 포스팅 미리보기 보기
                        </button>
                    </div>
                </div>
                
                <footer class="tweet-footer">
                    <a href="${tweet.tweet_url}" target="_blank" rel="noopener noreferrer" class="tweet-link">
                        <i class="fab fa-twitter"></i>
                        원본 포스팅 보기
                    </a>
                    <div class="tweet-actions">
                        <button type="button" class="tweet-action" title="공유">
                            <i class="fas fa-share"></i>
                        </button>
                        <button type="button" class="tweet-action" title="북마크">
                            <i class="far fa-bookmark"></i>
                        </button>
                    </div>
                </footer>
            </article>
        `;
    }

    renderPagination(data) {
        if (!this.contentElements.paginationContainer) return;
        
        const totalPages = Math.ceil(data.total / this.tweetsPerPage);
        
        if (totalPages <= 1) {
            this.contentElements.paginationContainer.innerHTML = '';
            return;
        }

        let paginationHtml = '<ul class="pagination">';
        
        // 이전 페이지
        const prevDisabled = this.currentPage <= 1 ? 'disabled' : '';
        paginationHtml += `
            <li class="pagination-item ${prevDisabled}">
                <a href="#" class="pagination-link" data-page="${this.currentPage - 1}">
                    <i class="fas fa-chevron-left"></i>
                </a>
            </li>
        `;
        
        // 페이지 번호
        const startPage = Math.max(1, this.currentPage - 2);
        const endPage = Math.min(totalPages, this.currentPage + 2);
        
        if (startPage > 1) {
            paginationHtml += `
                <li class="pagination-item">
                    <a href="#" class="pagination-link" data-page="1">1</a>
                </li>
            `;
            if (startPage > 2) {
                paginationHtml += '<li class="pagination-item"><span class="pagination-link">...</span></li>';
            }
        }
        
        for (let i = startPage; i <= endPage; i++) {
            const activeClass = i === this.currentPage ? 'active' : '';
            paginationHtml += `
                <li class="pagination-item ${activeClass}">
                    <a href="#" class="pagination-link" data-page="${i}">${i}</a>
                </li>
            `;
        }
        
        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                paginationHtml += '<li class="pagination-item"><span class="pagination-link">...</span></li>';
            }
            paginationHtml += `
                <li class="pagination-item">
                    <a href="#" class="pagination-link" data-page="${totalPages}">${totalPages}</a>
                </li>
            `;
        }
        
        // 다음 페이지
        const nextDisabled = this.currentPage >= totalPages ? 'disabled' : '';
        paginationHtml += `
            <li class="pagination-item ${nextDisabled}">
                <a href="#" class="pagination-link" data-page="${this.currentPage + 1}">
                    <i class="fas fa-chevron-right"></i>
                </a>
            </li>
        `;
        
        paginationHtml += '</ul>';
        
        this.contentElements.paginationContainer.innerHTML = paginationHtml;
        
        // 페이지네이션 클릭 이벤트
        this.contentElements.paginationContainer.addEventListener('click', (e) => {
            e.preventDefault();
            const link = e.target.closest('.pagination-link');
            if (link && !link.closest('.pagination-item').classList.contains('disabled')) {
                const page = parseInt(link.getAttribute('data-page'));
                if (page && page !== this.currentPage) {
                    this.currentPage = page;
                    this.loadTweets();
                }
            }
        });
    }

    // 이벤트 핸들러
    toggleHelp() {
        const content = this.helpElements.content;
        const toggle = this.helpElements.toggle;
        
        if (content && toggle) {
            const isActive = content.classList.contains('active');
            
            if (isActive) {
                content.classList.remove('active');
                toggle.innerHTML = '<i class="fas fa-chevron-down"></i>';
            } else {
                content.classList.add('active');
                toggle.innerHTML = '<i class="fas fa-chevron-up"></i>';
            }
        }
    }

    toggleFilters() {
        const content = this.filterElements.content;
        const toggle = this.filterElements.toggle;
        
        if (content && toggle) {
            const isCollapsed = content.classList.contains('collapsed');
            
            if (isCollapsed) {
                content.classList.remove('collapsed');
                toggle.innerHTML = '<i class="fas fa-chevron-up"></i>';
            } else {
                content.classList.add('collapsed');
                toggle.innerHTML = '<i class="fas fa-chevron-down"></i>';
            }
        }
    }

    handleSearch() {
        if (this.filterElements.search) {
            this.filters.search = this.filterElements.search.value.trim();
            this.currentPage = 1;
            this.loadTweets();
        }
    }

    handleFilterChange() {
        // 필터 값 업데이트
        if (this.filterElements.userSelect) {
            this.filters.user_id = this.filterElements.userSelect.value || null;
        }
        if (this.filterElements.tagSelect) {
            this.filters.tag = this.filterElements.tagSelect.value || '';
        }
        if (this.filterElements.dateFrom) {
            this.filters.date_from = this.filterElements.dateFrom.value || '';
        }
        if (this.filterElements.dateTo) {
            this.filters.date_to = this.filterElements.dateTo.value || '';
        }
        if (this.filterElements.sortSelect) {
            this.filters.sort_by = this.filterElements.sortSelect.value || 'newest';
        }

        this.currentPage = 1;
        this.loadTweets();
    }

    filterByTag(tagName) {
        if (this.filterElements.tagSelect) {
            this.filterElements.tagSelect.value = tagName;
            this.filters.tag = tagName;
            this.currentPage = 1;
            this.loadTweets();
            
            // 필터 섹션 열기
            if (this.filterElements.content?.classList.contains('collapsed')) {
                this.toggleFilters();
            }
        }
    }

    handleDateRangeChange() {
        const range = this.filterElements.dateRange.value;
        const customGroups = document.querySelectorAll('.date-custom-group');
        
        if (range === 'custom') {
            // 직접 선택 시 날짜 입력 필드 표시
            customGroups.forEach(group => group.style.display = 'flex');
        } else {
            // 다른 옵션 선택 시 날짜 입력 필드 숨김
            customGroups.forEach(group => group.style.display = 'none');
            
            // 선택된 범위에 따라 날짜 설정
            const today = new Date();
            let fromDate = null;
            let toDate = today.toISOString().split('T')[0];
            
            switch(range) {
                case 'today':
                    fromDate = toDate;
                    break;
                case 'yesterday':
                    const yesterday = new Date(today);
                    yesterday.setDate(yesterday.getDate() - 1);
                    fromDate = yesterday.toISOString().split('T')[0];
                    toDate = fromDate;
                    break;
                case 'week':
                    const weekAgo = new Date(today);
                    weekAgo.setDate(weekAgo.getDate() - 7);
                    fromDate = weekAgo.toISOString().split('T')[0];
                    break;
                case 'month':
                    const monthAgo = new Date(today);
                    monthAgo.setDate(monthAgo.getDate() - 30);
                    fromDate = monthAgo.toISOString().split('T')[0];
                    break;
                default:
                    fromDate = '';
                    toDate = '';
            }
            
            // 필터 값 업데이트
            this.filters.date_from = fromDate;
            this.filters.date_to = toDate;
            
            // 필터 적용
            this.currentPage = 1;
            this.loadTweets();
        }
    }

    resetFilters() {
        // 필터 초기화
        this.filters = {
            search: '',
            user_id: null,
            username: '',
            tag: '',
            tags: [],
            date_from: '',
            date_to: '',
            sort_by: 'newest'
        };

        // UI 초기화
        if (this.filterElements.search) this.filterElements.search.value = '';
        if (this.filterElements.userSelect) this.filterElements.userSelect.value = '';
        if (this.filterElements.tagSelect) this.filterElements.tagSelect.value = '';
        if (this.filterElements.dateRange) this.filterElements.dateRange.value = '';
        if (this.filterElements.dateFrom) this.filterElements.dateFrom.value = '';
        if (this.filterElements.dateTo) this.filterElements.dateTo.value = '';
        if (this.filterElements.sortSelect) this.filterElements.sortSelect.value = 'newest';

        // 커스텀 날짜 필드 숨기기
        const customGroups = document.querySelectorAll('.date-custom-group');
        customGroups.forEach(group => group.style.display = 'none');

        this.currentPage = 1;
        this.loadTweets();
    }

    // UI 상태 관리
    showLoading() {
        if (this.contentElements.loadingContainer) {
            this.contentElements.loadingContainer.style.display = 'block';
        }
        if (this.contentElements.tweetsGrid) {
            this.contentElements.tweetsGrid.classList.add('loading');
        }
    }

    hideLoading() {
        if (this.contentElements.loadingContainer) {
            this.contentElements.loadingContainer.style.display = 'none';
        }
        if (this.contentElements.tweetsGrid) {
            this.contentElements.tweetsGrid.classList.remove('loading');
        }
    }

    showEmpty() {
        if (this.contentElements.emptyState) {
            this.contentElements.emptyState.style.display = 'block';
        }
        if (this.contentElements.tweetsGrid) {
            this.contentElements.tweetsGrid.innerHTML = '';
        }
    }

    hideEmpty() {
        if (this.contentElements.emptyState) {
            this.contentElements.emptyState.style.display = 'none';
        }
    }

    showError(message) {
        console.error('Dashboard 오류:', message);
        
        if (this.contentElements.tweetsGrid) {
            this.contentElements.tweetsGrid.innerHTML = `
                <div class="error-message text-center">
                    <i class="fas fa-exclamation-triangle text-error"></i>
                    <p>${message}</p>
                    <button type="button" class="btn btn-secondary" onclick="dashboard.loadTweets()">
                        <i class="fas fa-redo"></i> 다시 시도
                    </button>
                </div>
            `;
        }
    }

    // 포스팅 미리보기 관련 함수
    extractTweetId(tweetUrl) {
        // Twitter URL에서 포스팅 ID 추출
        // https://twitter.com/user/status/1234567890 또는
        // https://x.com/user/status/1234567890 형식에서 ID 추출
        const match = tweetUrl.match(/(?:twitter|x)\.com\/[^/]+\/status\/(\d+)/);
        return match ? match[1] : null;
    }

    setupTweetPreviewListeners() {
        // 모달 미리보기 버튼에 이벤트 리스너 추가
        const previewButtons = document.querySelectorAll('.btn-modal-preview');
        
        previewButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const tweetId = e.target.getAttribute('data-tweet-id') || 
                               e.target.closest('.btn-modal-preview')?.getAttribute('data-tweet-id');
                
                if (tweetId) {
                    this.openTweetModal(tweetId);
                }
            });
        });
    }

    setupModalEventListeners() {
        // 모달 닫기 버튼
        if (this.modalElements.closeBtn) {
            this.modalElements.closeBtn.addEventListener('click', () => {
                this.closeTweetModal();
            });
        }

        // 모달 배경 클릭으로 닫기
        if (this.modalElements.backdrop) {
            this.modalElements.backdrop.addEventListener('click', () => {
                this.closeTweetModal();
            });
        }

        // 이전/다음 포스팅 네비게이션
        if (this.modalElements.prevBtn) {
            this.modalElements.prevBtn.addEventListener('click', () => {
                this.navigateModal(-1);
            });
        }

        if (this.modalElements.nextBtn) {
            this.modalElements.nextBtn.addEventListener('click', () => {
                this.navigateModal(1);
            });
        }

        // 키보드 이벤트 (ESC로 닫기, 방향키로 네비게이션)
        document.addEventListener('keydown', (e) => {
            if (this.modalElements.modal?.classList.contains('active')) {
                switch (e.key) {
                    case 'Escape':
                        this.closeTweetModal();
                        e.preventDefault();
                        break;
                    case 'ArrowLeft':
                        this.navigateModal(-1);
                        e.preventDefault();
                        break;
                    case 'ArrowRight':
                        this.navigateModal(1);
                        e.preventDefault();
                        break;
                }
            }
        });
    }

    async loadTweetEmbed(tweetId, embedId, buttonElement) {
        try {
            const embedContainer = document.getElementById(embedId);
            if (!embedContainer) return;

            // 버튼을 로딩 상태로 변경
            buttonElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 로딩 중...';
            buttonElement.disabled = true;

            // 기존 콘텐츠 제거
            embedContainer.innerHTML = '';

            // Twitter Embed 블록 생성
            const blockquoteElement = document.createElement('blockquote');
            blockquoteElement.className = 'twitter-tweet';
            blockquoteElement.setAttribute('data-theme', 'light');
            blockquoteElement.setAttribute('data-width', '100%');
            blockquoteElement.innerHTML = `
                <a href="https://twitter.com/i/status/${tweetId}">
                    포스팅을 불러오는 중...
                </a>
            `;

            embedContainer.appendChild(blockquoteElement);

            // Twitter 위젯 로드
            if (window.twttr && window.twttr.widgets) {
                await window.twttr.widgets.load(embedContainer);
                this.adjustTweetEmbedSize(embedContainer);
                console.log('✅ 포스팅 미리보기 로드 완료:', tweetId);
            } else {
                // twttr이 아직 로드되지 않은 경우 잠시 대기
                await this.waitForTwitterWidgets();
                if (window.twttr && window.twttr.widgets) {
                    await window.twttr.widgets.load(embedContainer);
                    this.adjustTweetEmbedSize(embedContainer);
                } else {
                    throw new Error('Twitter 위젯을 로드할 수 없습니다.');
                }
            }

        } catch (error) {
            console.error('포스팅 미리보기 로드 실패:', error);
            
            // 에러 시 원래 버튼으로 복구
            buttonElement.innerHTML = '<i class="fas fa-exclamation-triangle"></i> 로드 실패 - 다시 시도';
            buttonElement.disabled = false;
            
            // 에러 메시지 표시
            const embedContainer = document.getElementById(embedId);
            if (embedContainer) {
                embedContainer.innerHTML = `
                    <div class="tweet-preview-error">
                        <p><i class="fas fa-exclamation-triangle"></i> 포스팅을 불러올 수 없습니다.</p>
                        <button type="button" class="btn-load-preview" data-tweet-id="${tweetId}" data-embed-id="${embedId}">
                            <i class="fas fa-redo"></i> 다시 시도
                        </button>
                    </div>
                `;
                
                // 새 버튼에 이벤트 리스너 추가
                this.setupTweetPreviewListeners();
            }
        }
    }

    waitForTwitterWidgets() {
        return new Promise((resolve) => {
            let attempts = 0;
            const maxAttempts = 20;
            
            const checkTwitterWidgets = () => {
                attempts++;
                
                if (window.twttr && window.twttr.widgets) {
                    resolve();
                } else if (attempts < maxAttempts) {
                    setTimeout(checkTwitterWidgets, 500);
                } else {
                    resolve(); // 최대 시도 횟수 도달 시 포기
                }
            };
            
            checkTwitterWidgets();
        });
    }

    async loadTweetEmbedAuto(tweetId, embedId) {
        try {
            const embedContainer = document.getElementById(embedId);
            if (!embedContainer) return;

            // 기존 플레이스홀더 제거
            embedContainer.innerHTML = '';

            // Twitter Embed 블록 생성
            const blockquoteElement = document.createElement('blockquote');
            blockquoteElement.className = 'twitter-tweet';
            blockquoteElement.setAttribute('data-theme', 'light');
            blockquoteElement.setAttribute('data-width', '100%');
            blockquoteElement.innerHTML = `
                <a href="https://twitter.com/i/status/${tweetId}">
                    포스팅을 불러오는 중...
                </a>
            `;

            embedContainer.appendChild(blockquoteElement);

            // Twitter 위젯 로드
            if (window.twttr && window.twttr.widgets) {
                await window.twttr.widgets.load(embedContainer);
                this.adjustTweetEmbedSize(embedContainer);
            } else {
                await this.waitForTwitterWidgets();
                if (window.twttr && window.twttr.widgets) {
                    await window.twttr.widgets.load(embedContainer);
                    this.adjustTweetEmbedSize(embedContainer);
                }
            }

        } catch (error) {
            console.error('포스팅 자동 로드 실패:', error);
            // 에러 시 조용히 실패 (UI에 영향 없음)
        }
    }

    adjustTweetEmbedSize(embedContainer) {
        // 트위터 위젯이 로드된 후 크기 조정
        setTimeout(() => {
            const tweetFrames = embedContainer.querySelectorAll('iframe');
            const tweetElements = embedContainer.querySelectorAll('.twitter-tweet');
            
            tweetFrames.forEach(frame => {
                frame.style.maxHeight = '400px';
                frame.style.height = 'auto';
                frame.style.width = '100%';
            });

            tweetElements.forEach(tweet => {
                tweet.style.maxHeight = '400px';
                tweet.style.overflow = 'hidden';
                tweet.style.width = '100%';
            });
        }, 1000); // 1초 후 크기 조정
    }

    // 유틸리티 함수
    formatDate(dateString) {
        if (!dateString) return '';
        
        try {
            const date = new Date(dateString);
            return new Intl.DateTimeFormat('ko-KR', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            }).format(date);
        } catch (error) {
            return dateString;
        }
    }

    escapeHtml(text) {
        if (!text) return '';
        
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 모달 관련 함수들
    openTweetModal(tweetId) {
        // 현재 포스팅 인덱스 찾기
        const tweetIndex = this.currentTweetsData.findIndex(tweet => 
            this.extractTweetId(tweet.tweet_url) === tweetId
        );
        
        if (tweetIndex === -1) {
            console.error('포스팅을 찾을 수 없습니다:', tweetId);
            return;
        }

        this.currentModalTweetIndex = tweetIndex;
        const tweet = this.currentTweetsData[tweetIndex];
        
        // 모달 정보 업데이트
        this.updateModalContent(tweet);
        
        // 모달 표시
        if (this.modalElements.modal) {
            this.modalElements.modal.classList.add('active');
            document.body.classList.add('modal-open');
        }
        
        // 임베드 컨테이너 스크롤을 맨 위로 이동
        const embedContainer = document.getElementById('modal-tweet-embed');
        if (embedContainer) {
            embedContainer.scrollTop = 0;
        }
        
        // 포스팅 임베드 로드
        this.loadModalTweetEmbed(tweetId);
        
        // 네비게이션 버튼 상태 업데이트
        this.updateModalNavigation();
    }

    closeTweetModal() {
        if (this.modalElements.modal) {
            this.modalElements.modal.classList.remove('active');
            document.body.classList.remove('modal-open');
        }
        
        // 임베드 컨테이너 초기화
        if (this.modalElements.embedContainer) {
            this.modalElements.embedContainer.innerHTML = `
                <div class="tweet-embed-loading">
                    <i class="fas fa-spinner fa-spin"></i>
                    <span>포스팅을 불러오는 중...</span>
                </div>
            `;
        }
        
        this.currentModalTweetIndex = -1;
    }

    navigateModal(direction) {
        const newIndex = this.currentModalTweetIndex + direction;
        
        if (newIndex >= 0 && newIndex < this.currentTweetsData.length) {
            this.currentModalTweetIndex = newIndex;
            const tweet = this.currentTweetsData[newIndex];
            const tweetId = this.extractTweetId(tweet.tweet_url);
            
            // 모달 콘텐츠 업데이트
            this.updateModalContent(tweet);
            
            // 임베드 컨테이너 스크롤을 맨 위로 이동
            const embedContainer = document.getElementById('modal-tweet-embed');
            if (embedContainer) {
                embedContainer.scrollTop = 0;
            }
            
            // 새 포스팅 임베드 로드
            this.loadModalTweetEmbed(tweetId);
            
            // 네비게이션 버튼 상태 업데이트
            this.updateModalNavigation();
        }
    }

    updateModalContent(tweet) {
        const userInitial = (tweet.user?.display_name || tweet.user?.telegram_username || '?')[0].toUpperCase();
        const userName = tweet.user?.display_name || tweet.user?.telegram_username || 'Unknown';
        const tweetDate = this.formatDate(tweet.created_at);
        const comment = tweet.comment || '';
        const tags = tweet.tags || [];

        // 사용자 정보 업데이트
        if (this.modalElements.userAvatar) {
            this.modalElements.userAvatar.textContent = userInitial;
        }
        if (this.modalElements.userName) {
            this.modalElements.userName.textContent = userName;
        }
        if (this.modalElements.tweetDate) {
            this.modalElements.tweetDate.textContent = tweetDate;
        }

        // 코멘트 업데이트
        if (this.modalElements.tweetComment) {
            this.modalElements.tweetComment.textContent = comment;
            this.modalElements.tweetComment.style.display = comment ? 'block' : 'none';
        }

        // 태그 업데이트
        if (this.modalElements.tweetTags) {
            if (tags.length > 0) {
                const tagsHtml = tags.map(tag => 
                    `<span class="modal-tag">#${tag.name}</span>`
                ).join('');
                this.modalElements.tweetTags.innerHTML = tagsHtml;
                this.modalElements.tweetTags.style.display = 'block';
            } else {
                this.modalElements.tweetTags.style.display = 'none';
            }
        }

        // 원본 링크 업데이트
        if (this.modalElements.tweetLink) {
            this.modalElements.tweetLink.href = tweet.tweet_url;
        }
    }

    updateModalNavigation() {
        // 이전 버튼 상태
        if (this.modalElements.prevBtn) {
            this.modalElements.prevBtn.disabled = this.currentModalTweetIndex <= 0;
        }
        
        // 다음 버튼 상태
        if (this.modalElements.nextBtn) {
            this.modalElements.nextBtn.disabled = this.currentModalTweetIndex >= this.currentTweetsData.length - 1;
        }
    }

    async loadModalTweetEmbed(tweetId) {
        try {
            if (!this.modalElements.embedContainer) return;

            // 로딩 상태 표시
            this.modalElements.embedContainer.innerHTML = `
                <div class="tweet-embed-loading">
                    <i class="fas fa-spinner fa-spin"></i>
                    <span>포스팅을 불러오는 중...</span>
                </div>
            `;

            // Twitter Embed 블록 생성
            const blockquoteElement = document.createElement('blockquote');
            blockquoteElement.className = 'twitter-tweet';
            blockquoteElement.setAttribute('data-theme', 'light');
            blockquoteElement.setAttribute('data-width', '100%');
            blockquoteElement.innerHTML = `
                <a href="https://twitter.com/i/status/${tweetId}">
                    포스팅을 불러오는 중...
                </a>
            `;

            // 로딩 표시 제거하고 임베드 추가
            this.modalElements.embedContainer.innerHTML = '';
            this.modalElements.embedContainer.appendChild(blockquoteElement);

            // Twitter 위젯 로드
            if (window.twttr && window.twttr.widgets) {
                await window.twttr.widgets.load(this.modalElements.embedContainer);
                console.log('✅ 모달 포스팅 임베드 로드 완료:', tweetId);
            } else {
                await this.waitForTwitterWidgets();
                if (window.twttr && window.twttr.widgets) {
                    await window.twttr.widgets.load(this.modalElements.embedContainer);
                } else {
                    throw new Error('Twitter 위젯을 로드할 수 없습니다.');
                }
            }

        } catch (error) {
            console.error('모달 포스팅 임베드 로드 실패:', error);
            
            // 에러 메시지 표시
            if (this.modalElements.embedContainer) {
                this.modalElements.embedContainer.innerHTML = `
                    <div class="tweet-embed-error">
                        <i class="fas fa-exclamation-triangle"></i>
                        <p>포스팅을 불러올 수 없습니다.</p>
                        <button type="button" class="btn btn-secondary" onclick="dashboard.loadModalTweetEmbed('${tweetId}')">
                            <i class="fas fa-redo"></i> 다시 시도
                        </button>
                    </div>
                `;
            }
        }
    }
}

// 전역 인스턴스
let dashboard;

// DOM 로드 후 초기화
document.addEventListener('DOMContentLoaded', function() {
    console.log('🌟 DOM 로드 완료 - Dashboard 초기화 시작');
    dashboard = new Dashboard();
    // 전역 함수 (HTML에서 호출 가능)
    window.dashboard = dashboard;
});