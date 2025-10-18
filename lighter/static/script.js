// 간단한 해시 함수
function simpleHash(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // 32bit 정수로 변환
    }
    return Math.abs(hash).toString(36);
}

// 잔액 추적을 위한 로컬스토리지 함수들
function saveBalanceSnapshot(addresses, accountsData) {
    const timestamp = new Date().toISOString();
    // 원본 배열을 변경하지 않고 정렬된 복사본 생성
    const addressKey = [...addresses].sort().join('|');
    
    // 전체 자산 계산
    const totalBalance = accountsData.reduce((sum, acc) => sum + parseFloat(acc.total_asset_value), 0);
    const totalPnL = accountsData.reduce((sum, acc) => {
        return sum + acc.positions.reduce((pnlSum, pos) => pnlSum + parseFloat(pos.unrealized_pnl), 0);
    }, 0);
    
    const snapshot = {
        timestamp,
        totalBalance,
        totalPnL,
        accountCount: accountsData.length,
        addressKey: addressKey, // 디버깅용
        accounts: accountsData.map(acc => ({
            address: acc.l1_address,
            balance: parseFloat(acc.total_asset_value),
            positions: acc.positions.length
        }))
    };
    
    // 기존 히스토리 가져오기
    const historyKey = `lighter_history_${simpleHash(addressKey)}`;
    let history = JSON.parse(localStorage.getItem(historyKey) || '[]');
    
    // 새 스냅샷 추가 (최대 100개까지만 보관)
    history.push(snapshot);
    if (history.length > 100) {
        history = history.slice(-100);
    }
    
    localStorage.setItem(historyKey, JSON.stringify(history));
    
    // 디버깅을 위해 콘솔에 출력
    console.log('Saved snapshot:', {
        addressKey,
        historyKey,
        accountCount: accountsData.length,
        historyLength: history.length
    });
    
    return historyKey;
}

function getBalanceHistory(addresses) {
    const addressKey = [...addresses].sort().join('|');
    const historyKey = `lighter_history_${simpleHash(addressKey)}`;
    const history = JSON.parse(localStorage.getItem(historyKey) || '[]');
    
    // 디버깅을 위해 콘솔에 출력
    console.log('Retrieved history:', {
        addressKey,
        historyKey,
        accountCount: addresses.length,
        historyLength: history.length
    });
    
    return history;
}

function clearBalanceHistory(addresses) {
    const addressKey = [...addresses].sort().join('|');
    const historyKey = `lighter_history_${simpleHash(addressKey)}`;
    localStorage.removeItem(historyKey);
    
    console.log('Cleared history:', {
        addressKey,
        historyKey,
        accountCount: addresses.length
    });
}

async function checkPoints() {
    const addressInput = document.getElementById('addressInput');
    const resultsDiv = document.getElementById('results');
    const checkButton = document.getElementById('checkButton');
    
    // 입력된 주소들을 줄바꿈으로 분리
    const addresses = addressInput.value
        .split('\n')
        .map(addr => addr.trim())
        .filter(addr => addr.length > 0);
    
    if (addresses.length === 0) {
        resultsDiv.innerHTML = '<div class="error">주소를 입력해주세요.</div>';
        return;
    }
    
    if (addresses.length > 100) {
        resultsDiv.innerHTML = '<div class="error">최대 100개의 주소만 조회할 수 있습니다.</div>';
        return;
    }
    
    // 로딩 상태
    checkButton.disabled = true;
    resultsDiv.innerHTML = '<div class="loading">데이터를 불러오는 중...</div>';
    
    try {
        const response = await fetch('/lighter/api/fetch_accounts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ addresses })
        });
        
        if (!response.ok) {
            throw new Error('데이터를 가져오는데 실패했습니다.');
        }
        
        const data = await response.json();

        // 잔액 스냅샷 저장
        if (data.accounts && data.accounts.length > 0) {
            saveBalanceSnapshot(addresses, data.accounts);
        }

        displayResults(data.accounts, data.position_summary, addresses, data.market_prices);
        
    } catch (error) {
        resultsDiv.innerHTML = `<div class="error">오류: ${error.message}</div>`;
    } finally {
        checkButton.disabled = false;
    }
}

let currentView = 'table'; // 'table' or 'card'

function displayResults(accounts, positionSummary, addresses, marketPrices) {
    const resultsDiv = document.getElementById('results');

    if (!accounts || accounts.length === 0) {
        resultsDiv.innerHTML = '<div class="error">조회된 계정이 없습니다.</div>';
        return;
    }

    let html = '';

    // 잔액 히스토리 차트 추가
    const history = getBalanceHistory(addresses);
    if (history.length > 1) {
        html += createBalanceHistoryChart(history, addresses);
    }

    // marketPrices를 window에 저장하여 테이블에서 사용
    window.currentMarketPrices = marketPrices;

    // 계정 비교 대시보드 추가
    html += createAccountComparisonDashboard(accounts);
    
    // 뷰 전환 버튼
    html += `
        <div class="view-controls">
            <button class="view-btn ${currentView === 'table' ? 'active' : ''}" onclick="switchView('table')">테이블 뷰</button>
            <button class="view-btn ${currentView === 'card' ? 'active' : ''}" onclick="switchView('card')">카드 뷰</button>
        </div>
    `;
    
    // 포지션 요약 섹션
    if (positionSummary && Object.keys(positionSummary).length > 0) {
        html += `
            <div class="summary-card">
                <h2 class="summary-title">전체 포지션 요약 (균형 포지션 확인)</h2>
                <div class="summary-grid">
                    ${Object.entries(positionSummary).map(([symbol, data]) => {
                        const netPosition = data.net_position.toFixed(4);
                        const isNeutral = Math.abs(data.net_position) < 0.01;
                        const neutralClass = isNeutral ? 'neutral' : (data.net_position > 0 ? 'long-bias' : 'short-bias');
                        
                        return `
                            <div class="summary-item ${neutralClass}">
                                <div class="summary-symbol">${symbol}</div>
                                <div class="summary-details">
                                    <div class="summary-row">
                                        <span>Net Position:</span>
                                        <span class="net-position">${netPosition > 0 ? '+' : ''}${netPosition}</span>
                                    </div>
                                    <div class="summary-row">
                                        <span>Total Value:</span>
                                        <span>$${data.total_value.toFixed(2)}</span>
                                    </div>
                                    <div class="summary-row">
                                        <span>포지션 수:</span>
                                        <span>${data.long_count} Long / ${data.short_count} Short</span>
                                    </div>
                                    ${isNeutral ? '<div class="neutral-badge">✓ 균형 포지션</div>' : ''}
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    }
    
    // 테이블 뷰 또는 카드 뷰
    if (currentView === 'table') {
        html += createTableView(accounts);
    } else {
        // 기존 카드 뷰
        // 지갑 주소별로 인덱스 매핑 생성
        const walletIndexMap = {};
        let walletIndex = 1;

        accounts.forEach((account) => {
            if (!walletIndexMap[account.l1_address]) {
                walletIndexMap[account.l1_address] = walletIndex++;
            }
        });

        accounts.forEach((account, index) => {
            const totalBalance = parseFloat(account.total_asset_value).toFixed(2);
            const accountTypeLabel = account.account_type_label || (account.account_type === 0 ? 'Main' : `Sub-${account.account_type || 1}`);
            const typeClass = account.account_type === 0 ? 'main-account' : 'sub-account';
            const displayIndex = walletIndexMap[account.l1_address];

            html += `
                <div class="account-card ${typeClass}">
                    <div class="account-header">
                        <div>
                            <div class="account-address">
                                ${displayIndex}_${account.l1_address}
                                <span class="account-type-badge">${accountTypeLabel}</span>
                            </div>
                            <div style="margin-top: 8px; color: #9ca3af;">
                                Cross Asset Value: $${parseFloat(account.cross_asset_value).toFixed(2)}
                            </div>
                        </div>
                        <div class="total-balance">
                            <span>$</span>
                            <span>${totalBalance}</span>
                        </div>
                    </div>
                    
                    ${account.positions && account.positions.length > 0 ? `
                        <div class="positions-header">
                            <span>→</span>
                            <span>Open Positions</span>
                        </div>
                        <div class="positions-grid">
                            ${account.positions.map(position => createPositionCard(position)).join('')}
                        </div>
                    ` : '<div style="text-align: center; color: #9ca3af; padding: 20px;">포지션이 없습니다.</div>'}
                </div>
            `;
        });
    }
    
    resultsDiv.innerHTML = html;
    
    // 저장된 데이터 보관 (뷰 전환시 재사용)
    window.lastAccountsData = accounts;
    window.lastPositionSummary = positionSummary;
    window.lastAddresses = addresses;
}

// 잔액 히스토리 차트 생성 함수
function createBalanceHistoryChart(history, addresses) {
    const chartId = 'balanceHistoryChart';
    
    let html = `
        <div class="balance-history-section">
            <div class="history-header">
                <h2 class="history-title">
                    <i class="fas fa-chart-area"></i> 자산 변화 추이
                </h2>
                <div class="history-controls">
                    <button class="history-btn" onclick="exportBalanceData()" title="데이터 내보내기">
                        <i class="fas fa-download"></i> 내보내기
                    </button>
                    <button class="history-btn danger" onclick="clearHistoryData()" title="히스토리 삭제">
                        <i class="fas fa-trash"></i> 초기화
                    </button>
                </div>
            </div>
            
            <div class="history-stats">
                <div class="history-stat">
                    <span class="stat-label">추적 기간</span>
                    <span class="stat-value">${calculateTrackingPeriod(history)}</span>
                </div>
                <div class="history-stat">
                    <span class="stat-label">데이터 포인트</span>
                    <span class="stat-value">${history.length}개</span>
                </div>
                <div class="history-stat">
                    <span class="stat-label">최고점</span>
                    <span class="stat-value">$${Math.max(...history.map(h => h.totalBalance)).toFixed(2)}</span>
                </div>
                <div class="history-stat">
                    <span class="stat-label">최저점</span>
                    <span class="stat-value">$${Math.min(...history.map(h => h.totalBalance)).toFixed(2)}</span>
                </div>
            </div>
            
            <div class="chart-container">
                <canvas id="${chartId}" height="300"></canvas>
            </div>
        </div>
    `;
    
    // 차트 생성을 위한 데이터 저장
    setTimeout(() => {
        createLineChart(chartId, history);
    }, 100);
    
    return html;
}

// 추적 기간 계산 함수
function calculateTrackingPeriod(history) {
    if (history.length < 2) return '방금 시작';
    
    const first = new Date(history[0].timestamp);
    const last = new Date(history[history.length - 1].timestamp);
    const diffDays = Math.ceil((last - first) / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return '오늘';
    if (diffDays === 1) return '1일';
    if (diffDays < 30) return `${diffDays}일`;
    if (diffDays < 365) return `${Math.ceil(diffDays / 30)}개월`;
    return `${Math.ceil(diffDays / 365)}년`;
}

// 라인 차트 생성 함수
function createLineChart(chartId, history) {
    const ctx = document.getElementById(chartId);
    if (!ctx) return;

    // 기존 차트가 있다면 파괴
    if (window.balanceChart) {
        window.balanceChart.destroy();
    }

    // 데이터 준비
    const labels = history.map(h => {
        const date = new Date(h.timestamp);
        return date.toLocaleDateString('ko-KR', { 
            month: 'short', 
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    });

    const balanceData = history.map(h => h.totalBalance);
    const pnlData = history.map(h => h.totalPnL);

    // Chart.js 라인 차트 생성
    window.balanceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '총 자산',
                    data: balanceData,
                    borderColor: '#f9a826',
                    backgroundColor: 'rgba(249, 168, 38, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.3,
                    yAxisID: 'y'
                },
                {
                    label: '총 PnL',
                    data: pnlData,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.3,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        color: '#ffffff',
                        font: { size: 14 }
                    }
                },
                tooltip: {
                    backgroundColor: '#1e1f2b',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: '#f9a826',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    ticks: {
                        color: '#9ca3af',
                        maxTicksLimit: 8
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    ticks: {
                        color: '#f9a826',
                        callback: function(value) {
                            return '$' + value.toFixed(0);
                        }
                    },
                    grid: {
                        color: 'rgba(249, 168, 38, 0.1)'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    ticks: {
                        color: '#10b981',
                        callback: function(value) {
                            return (value >= 0 ? '+' : '') + '$' + value.toFixed(0);
                        }
                    },
                    grid: {
                        drawOnChartArea: false,
                    },
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            }
        }
    });
}

function createPositionCard(position) {
    const pnl = parseFloat(position.unrealized_pnl);
    const pnlClass = pnl >= 0 ? 'positive' : 'negative';
    const pnlSign = pnl >= 0 ? '+' : '';
    const positionType = position.sign === 1 ? 'Long' : 'Short';
    const typeClass = position.sign === 1 ? '' : 'short';
    
    // PnL 퍼센트 계산
    const positionValue = parseFloat(position.position_value);
    const pnlPercentage = positionValue > 0 ? (pnl / positionValue * 100).toFixed(2) : '0.00';
    
    return `
        <div class="position-card">
            <div class="position-header">
                <span class="position-type ${typeClass}">${positionType}</span>
                <span class="leverage-badge">${position.leverage || '1x'}</span>
            </div>
            
            <h3 class="symbol">${position.symbol}</h3>
            
            <div class="position-details">
                <div class="detail-row">
                    <span class="detail-label">Size:</span>
                    <span class="detail-value">${parseFloat(position.position).toFixed(2)}</span>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">Entry:</span>
                    <span class="detail-value">$${parseFloat(position.avg_entry_price).toFixed(2)}</span>
                </div>

                <div class="detail-row">
                    <span class="detail-label">현재가격:</span>
                    <span class="detail-value">${position.current_price ? `$${position.current_price.toFixed(2)}` : '-'}</span>
                </div>

                <div class="detail-row">
                    <span class="detail-label">Value:</span>
                    <span class="detail-value">$${parseFloat(position.position_value).toFixed(2)}</span>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">PnL:</span>
                    <span class="detail-value pnl-value ${pnlClass}">
                        <span>${pnlSign}$${Math.abs(pnl).toFixed(2)}</span>
                        <span class="pnl-percentage">${pnlSign}${pnlPercentage}%</span>
                    </span>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">청산가격:</span>
                    <span class="detail-value">$${parseFloat(position.liquidation_price).toFixed(2)}</span>
                </div>
            </div>
        </div>
    `;
}

// 테이블 뷰 생성 함수
function createTableView(accounts) {
    // 모든 포지션을 하나의 배열로 수집
    let allPositions = [];
    const colors = ['#8b5cf6', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#6366f1', '#14b8a6', '#f97316'];
    const accountColors = {};
    const accountIndexes = {}; // 지갑 주소별 인덱스 저장

    // 지갑 주소별로 인덱스 매핑 생성 (동일 주소는 같은 인덱스)
    let walletIndex = 1;
    const processedAddresses = new Set();

    accounts.forEach((account) => {
        if (!processedAddresses.has(account.l1_address)) {
            accountColors[account.l1_address] = colors[(walletIndex - 1) % colors.length];
            accountIndexes[account.l1_address] = walletIndex;
            processedAddresses.add(account.l1_address);
            walletIndex++;
        }
    });

    accounts.forEach((account, index) => {
        const accountTypeLabel = account.account_type_label || (account.account_type === 0 ? 'Main' : `Sub-${account.account_type || 1}`);
        const displayIndex = accountIndexes[account.l1_address];

        account.positions.forEach(position => {
            allPositions.push({
                ...position,
                account_address: account.l1_address,
                account_index: displayIndex,  // 지갑 주소 기준 인덱스 사용
                account_balance: account.total_asset_value,
                account_type: account.account_type,
                account_type_label: accountTypeLabel
            });
        });
    });
    
    // 심볼별로 정렬
    allPositions.sort((a, b) => a.symbol.localeCompare(b.symbol));
    
    let html = `
        <div class="table-container">
            <table class="positions-table">
                <thead>
                    <tr>
                        <th>계정</th>
                        <th>심볼</th>
                        <th>타입</th>
                        <th>수량</th>
                        <th>진입</th>
                        <th>현재</th>
                        <th>가치</th>
                        <th>PnL</th>
                        <th>레버</th>
                        <th>청산</th>
                        <th>리스크</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    allPositions.forEach(position => {
        const pnl = parseFloat(position.unrealized_pnl);
        const pnlClass = pnl >= 0 ? 'positive' : 'negative';
        const pnlSign = pnl >= 0 ? '+' : '';
        const positionType = position.sign === 1 ? 'Long' : 'Short';
        const typeClass = position.sign === 1 ? 'long' : 'short';
        const accountColor = accountColors[position.account_address];

        // PnL 퍼센트 계산
        const positionValue = parseFloat(position.position_value);
        const pnlPercentage = positionValue > 0 ? (pnl / positionValue * 100).toFixed(2) : '0.00';

        // 현재가격 추가
        const currentPrice = position.current_price || 0;

        html += `
            <tr>
                <td>
                    <div class="account-cell">
                        <div class="account-indicator" style="background-color: ${accountColor}"></div>
                        <span class="account-short">${position.account_index}_${position.account_address.substring(2, 6)}</span>
                        <span class="account-type-mini">(${position.account_type_label})</span>
                    </div>
                </td>
                <td class="symbol-cell">${position.symbol}</td>
                <td><span class="position-badge ${typeClass}">${positionType}</span></td>
                <td>${parseFloat(position.position).toFixed(3)}</td>
                <td>$${parseFloat(position.avg_entry_price).toFixed(3)}</td>
                <td>${currentPrice ? `$${currentPrice.toFixed(3)}` : '-'}</td>
                <td>$${parseFloat(position.position_value).toFixed(3)}</td>
                <td class="pnl-cell ${pnlClass}">
                    ${pnlSign}$${Math.abs(pnl).toFixed(3)}
                    <br><span class="pnl-percentage" style="font-size: 0.75rem;">${pnlSign}${pnlPercentage}%</span>
                </td>
                <td><span class="leverage-badge">${position.leverage || '1x'}</span></td>
                <td>$${parseFloat(position.liquidation_price).toFixed(3)}</td>
                <td class="liquidation-percent-cell">${formatLiquidationPercent(position)}</td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
        
        <div class="account-legend">
            <h3>계정 목록</h3>
            <div class="legend-items">
                ${accounts.map((account, index) => {
                    const accountTypeLabel = account.account_type_label || (account.account_type === 0 ? 'Main' : `Sub-${account.account_type || 1}`);
                    const displayIndex = accountIndexes[account.l1_address];
                    const colorIndex = displayIndex - 1;
                    return `
                        <div class="legend-item">
                            <div class="account-indicator" style="background-color: ${colors[colorIndex % colors.length]}"></div>
                            <div>
                                <div class="legend-address">
                                    ${displayIndex}_${account.l1_address}
                                    <span class="account-type-badge-small">${accountTypeLabel}</span>
                                </div>
                                <div class="legend-balance">Balance: $${parseFloat(account.total_asset_value).toFixed(2)}</div>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
    
    return html;
}

// 뷰 전환 함수
function switchView(view) {
    currentView = view;
    if (window.lastAccountsData && window.lastPositionSummary && window.lastAddresses) {
        displayResults(window.lastAccountsData, window.lastPositionSummary, window.lastAddresses);
    }
}

// 데이터 내보내기 함수
function exportBalanceData() {
    if (!window.lastAddresses) {
        alert('내보낼 데이터가 없습니다.');
        return;
    }
    
    const history = getBalanceHistory(window.lastAddresses);
    if (history.length === 0) {
        alert('내보낼 히스토리가 없습니다.');
        return;
    }
    
    // CSV 형식으로 데이터 준비
    const csvHeaders = ['날짜', '총자산', 'PnL', '계정수'];
    const csvRows = history.map(h => [
        new Date(h.timestamp).toLocaleString('ko-KR'),
        h.totalBalance.toFixed(2),
        h.totalPnL.toFixed(2),
        h.accountCount
    ]);
    
    const csvContent = [csvHeaders, ...csvRows]
        .map(row => row.join(','))
        .join('\n');
    
    // 파일 다운로드
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `lighter-balance-history-${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// 히스토리 초기화 함수
function clearHistoryData() {
    if (!window.lastAddresses) {
        alert('초기화할 데이터가 없습니다.');
        return;
    }
    
    if (confirm('모든 잔액 히스토리를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.')) {
        clearBalanceHistory(window.lastAddresses);
        alert('히스토리가 삭제되었습니다.');
        
        // 페이지 새로고침으로 UI 업데이트
        if (window.lastAccountsData && window.lastPositionSummary) {
            displayResults(window.lastAccountsData, window.lastPositionSummary, window.lastAddresses);
        }
    }
}


// 청산 퍼센트 포맷 함수
function formatLiquidationPercent(position) {
    if (position.liquidation_percent === null || position.liquidation_percent === undefined) {
        return '-';
    }

    const percent = Math.abs(position.liquidation_percent);
    const sign = position.sign;

    // 색상 결정 (10% 미만 위험, 10-20% 경고, 20% 이상 안전)
    let colorClass = '';
    if (percent < 10) {
        colorClass = 'danger';
    } else if (percent < 20) {
        colorClass = 'warning';
    } else {
        colorClass = 'safe';
    }

    // 방향 표시 (Long은 ↓, Short는 ↑)
    const direction = sign === 1 ? '↓' : '↑';

    return `<span class="liquidation-percent ${colorClass}">${direction} ${percent.toFixed(1)}%</span>`;
}

// 계정 비교 대시보드 생성 함수
function createAccountComparisonDashboard(accounts) {
    // 계정별 통계 계산
    const accountStats = accounts.map(account => {
        const totalBalance = parseFloat(account.total_asset_value);
        let totalPnL = 0;
        let openPositions = 0;
        let totalPositionValue = 0;
        
        account.positions.forEach(pos => {
            totalPnL += parseFloat(pos.unrealized_pnl);
            openPositions++;
            totalPositionValue += parseFloat(pos.position_value);
        });
        
        const pnlPercentage = totalPositionValue > 0 ? (totalPnL / totalPositionValue * 100) : 0;
        
        return {
            address: account.l1_address,
            totalBalance: totalBalance,
            totalPnL: totalPnL,
            pnlPercentage: pnlPercentage,
            openPositions: openPositions,
            crossAssetValue: parseFloat(account.cross_asset_value)
        };
    });
    
    // 전체 합계 계산
    const totalAssets = accountStats.reduce((sum, acc) => sum + acc.totalBalance, 0);
    const totalPnL = accountStats.reduce((sum, acc) => sum + acc.totalPnL, 0);
    const totalPositions = accountStats.reduce((sum, acc) => sum + acc.openPositions, 0);
    
    // PnL 기준으로 정렬
    accountStats.sort((a, b) => b.totalPnL - a.totalPnL);
    
    let html = `
        <div class="account-comparison-dashboard">
            <h2 class="dashboard-title">
                <i class="fas fa-chart-line"></i> 계정 비교 대시보드
            </h2>
            
            <!-- 전체 통계 -->
            <div class="total-stats">
                <div class="stat-card">
                    <div class="stat-label">전체 자산</div>
                    <div class="stat-value">$${totalAssets.toFixed(2)}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">전체 PnL</div>
                    <div class="stat-value ${totalPnL >= 0 ? 'positive' : 'negative'}">
                        ${totalPnL >= 0 ? '+' : ''}$${Math.abs(totalPnL).toFixed(2)}
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">총 포지션</div>
                    <div class="stat-value">${totalPositions}개</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">계정 수</div>
                    <div class="stat-value">${accounts.length}개</div>
                </div>
            </div>
            
            <!-- 계정별 비교 -->
            <div class="account-comparison-section">
                <div class="pie-chart-container">
                    <h3>자산 분포</h3>
                    <canvas id="assetPieChart" width="400" height="400"></canvas>
                </div>
                
                <div class="account-comparison-grid">
                    ${accountStats.map((acc, index) => {
                        const assetPercentage = (acc.totalBalance / totalAssets * 100).toFixed(1);
                        const pnlClass = acc.totalPnL >= 0 ? 'positive' : 'negative';
                        
                        return `
                            <div class="comparison-item">
                                <div class="comparison-header">
                                    <div class="account-rank">#${index + 1}</div>
                                    <div class="account-address-short">${acc.address.substring(0, 8)}...${acc.address.substring(acc.address.length - 6)}</div>
                                    <div class="account-pnl ${pnlClass}">
                                        ${acc.totalPnL >= 0 ? '+' : ''}$${Math.abs(acc.totalPnL).toFixed(2)}
                                        <span class="pnl-percentage">(${acc.pnlPercentage >= 0 ? '+' : ''}${acc.pnlPercentage.toFixed(2)}%)</span>
                                    </div>
                                </div>
                                
                                <div class="comparison-stats">
                                    <div class="stat-row">
                                        <span>자산:</span>
                                        <span>$${acc.totalBalance.toFixed(2)} (${assetPercentage}%)</span>
                                    </div>
                                    <div class="stat-row">
                                        <span>포지션:</span>
                                        <span>${acc.openPositions}개</span>
                                    </div>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        </div>
    `;
    
    // 파이 차트 생성을 위한 데이터 저장
    setTimeout(() => {
        createAssetPieChart(accountStats, totalAssets);
    }, 100);
    
    return html;
}

// 자산 분포 파이 차트 생성 함수
function createAssetPieChart(accountStats, totalAssets) {
    const ctx = document.getElementById('assetPieChart');
    if (!ctx) return;

    // 기존 차트가 있다면 파괴
    if (window.assetChart) {
        window.assetChart.destroy();
    }

    // 색상 팔레트
    const colors = [
        '#f9a826', '#10b981', '#3b82f6', '#ef4444', '#8b5cf6',
        '#f59e0b', '#14b8a6', '#6366f1', '#ec4899', '#84cc16'
    ];

    // 차트 데이터 준비
    const chartData = accountStats.map((acc, index) => ({
        label: `${acc.address.substring(0, 8)}...`,
        value: acc.totalBalance,
        percentage: (acc.totalBalance / totalAssets * 100).toFixed(1),
        color: colors[index % colors.length]
    }));

    // Chart.js 파이 차트 생성
    window.assetChart = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: chartData.map(item => item.label),
            datasets: [{
                data: chartData.map(item => item.value),
                backgroundColor: chartData.map(item => item.color),
                borderColor: '#1e1f2b',
                borderWidth: 2,
                hoverBorderWidth: 3,
                hoverBorderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#ffffff',
                        font: {
                            size: 12,
                            weight: '500'
                        },
                        padding: 20,
                        generateLabels: function(chart) {
                            return chartData.map((item, index) => ({
                                text: `${item.label} (${item.percentage}%)`,
                                fillStyle: item.color,
                                strokeStyle: item.color,
                                lineWidth: 0,
                                index: index,
                                fontColor: '#ffffff'
                            }));
                        }
                    }
                },
                tooltip: {
                    backgroundColor: '#1e1f2b',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: '#f9a826',
                    borderWidth: 1,
                    callbacks: {
                        label: function(context) {
                            const value = context.parsed;
                            const percentage = (value / totalAssets * 100).toFixed(1);
                            return `$${value.toFixed(2)} (${percentage}%)`;
                        }
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            }
        }
    });
}

// 엔터키로도 검색 가능하도록
document.getElementById('addressInput').addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && e.ctrlKey) {
        checkPoints();
    }
});