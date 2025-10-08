#!/usr/bin/env python3
import asyncio
import aiohttp
import json
from typing import List, Dict, Any
from datetime import datetime

API_URL = "http://localhost:8000/api/fetch_accounts"

def safe_float(value, default=0.0):
    """안전한 float 변환"""
    try:
        if isinstance(value, str):
            # 특수 문자나 잘못된 형식 처리
            value = value.replace(',', '').strip()
            if 'x' in value.lower() or value == '' or value == 'null' or value == 'None':
                return default
        return float(value)
    except (ValueError, TypeError):
        return default

async def fetch_portfolio(session: aiohttp.ClientSession, addresses: List[str]) -> Dict[str, Any]:
    """포트폴리오 데이터 가져오기"""
    data = {"addresses": addresses}
    async with session.post(API_URL, json=data) as response:
        return await response.json()

def analyze_positions(portfolio_data: Dict[str, Any]) -> Dict[str, Any]:
    """포지션 분석 및 통계 계산"""
    accounts = portfolio_data.get("accounts", [])

    # 전체 통계 초기화
    total_stats = {
        "total_wallets": len(accounts),
        "total_collateral": 0,
        "total_pnl": 0,
        "long_exposure": {},
        "short_exposure": {},
        "net_exposure": {},
        "wallet_analysis": []
    }

    # 각 지갑별 분석
    for idx, account in enumerate(accounts, 1):
        wallet_stats = {
            "index": idx,
            "address": account["l1_address"],
            "balance": safe_float(account.get("available_balance", 0)),
            "collateral": safe_float(account.get("collateral", 0)),
            "positions": [],
            "total_collateral": 0,
            "total_pnl": 0,
            "long_value": 0,
            "short_value": 0,
            "net_delta": 0
        }

        # 포지션 분석
        for pos in account.get("positions", []):
            # 포지션 필드 확인 및 기본값 설정
            average_entry = safe_float(pos.get("average_entry", 0))
            net_amount = safe_float(pos.get("net_amount", 0))
            position_value = abs(average_entry * net_amount)
            pnl = safe_float(pos.get("unrealized_pnl", 0))
            margin = safe_float(pos.get("margin", 0))
            current_price = safe_float(pos.get("current_price", average_entry))

            wallet_stats["total_collateral"] += margin
            wallet_stats["total_pnl"] += pnl

            # 토큰별 익스포저 계산
            token = pos.get("name", "Unknown")
            exposure = net_amount * current_price
            sign = pos.get("sign", 1)

            if sign == 1:  # Long
                wallet_stats["long_value"] += position_value
                if token not in total_stats["long_exposure"]:
                    total_stats["long_exposure"][token] = 0
                total_stats["long_exposure"][token] += exposure
            else:  # Short
                wallet_stats["short_value"] += position_value
                if token not in total_stats["short_exposure"]:
                    total_stats["short_exposure"][token] = 0
                total_stats["short_exposure"][token] += abs(exposure)

            wallet_stats["positions"].append({
                "token": token,
                "side": "LONG" if sign == 1 else "SHORT",
                "amount": net_amount,
                "entry": average_entry,
                "current": current_price,
                "pnl": pnl,
                "pnl_percent": safe_float(pos.get("pnl_percent", 0)),
                "leverage": safe_float(pos.get("leverage", 1)),
                "liquidation_percent": safe_float(pos.get("liquidation_percent", 0))
            })

        wallet_stats["net_delta"] = wallet_stats["long_value"] - wallet_stats["short_value"]

        # collateral이 없으면 available_balance 사용
        if wallet_stats["total_collateral"] == 0:
            wallet_stats["total_collateral"] = wallet_stats["collateral"]

        total_stats["wallet_analysis"].append(wallet_stats)
        total_stats["total_collateral"] += wallet_stats["total_collateral"]
        total_stats["total_pnl"] += wallet_stats["total_pnl"]

    # 전체 넷 익스포저 계산
    all_tokens = set(total_stats["long_exposure"].keys()) | set(total_stats["short_exposure"].keys())
    for token in all_tokens:
        long = total_stats["long_exposure"].get(token, 0)
        short = total_stats["short_exposure"].get(token, 0)
        total_stats["net_exposure"][token] = long - short

    # 전체 델타 계산
    total_stats["total_long"] = sum(total_stats["long_exposure"].values())
    total_stats["total_short"] = sum(total_stats["short_exposure"].values())
    total_stats["total_net_delta"] = total_stats["total_long"] - total_stats["total_short"]
    total_stats["delta_ratio"] = (total_stats["total_long"] / total_stats["total_short"]) if total_stats["total_short"] > 0 else float('inf')

    return total_stats

def calculate_correlation_metrics(wallet_analysis: List[Dict]) -> Dict[str, Any]:
    """지갑 간 상관관계 메트릭 계산"""
    correlation_metrics = {
        "position_overlap": {},
        "similar_strategies": [],
        "timing_patterns": []
    }

    # 포지션 중첩도 계산
    for i in range(len(wallet_analysis)):
        for j in range(i + 1, len(wallet_analysis)):
            wallet1 = wallet_analysis[i]
            wallet2 = wallet_analysis[j]

            tokens1 = {p["token"] + "_" + p["side"] for p in wallet1["positions"]}
            tokens2 = {p["token"] + "_" + p["side"] for p in wallet2["positions"]}

            overlap = len(tokens1 & tokens2)
            if overlap > 0:
                pair = f"Wallet_{i+1}_Wallet_{j+1}"
                correlation_metrics["position_overlap"][pair] = {
                    "overlapping_positions": overlap,
                    "similarity_score": overlap / max(len(tokens1), len(tokens2))
                }

    return correlation_metrics

def suggest_hedging_strategies(total_stats: Dict[str, Any]) -> List[Dict[str, str]]:
    """통계적 중립성을 위한 헷징 전략 제안"""
    suggestions = []

    # 1. 델타 중립성 확인
    net_delta = total_stats["total_net_delta"]
    if abs(net_delta) > total_stats["total_collateral"] * 0.1:
        if net_delta > 0:
            suggestions.append({
                "type": "DELTA_HEDGE",
                "action": "Increase SHORT positions or reduce LONG positions",
                "amount": f"${abs(net_delta):,.2f}",
                "priority": "HIGH"
            })
        else:
            suggestions.append({
                "type": "DELTA_HEDGE",
                "action": "Increase LONG positions or reduce SHORT positions",
                "amount": f"${abs(net_delta):,.2f}",
                "priority": "HIGH"
            })

    # 2. 토큰별 익스포저 밸런싱
    for token, net_exposure in total_stats["net_exposure"].items():
        if abs(net_exposure) > total_stats["total_collateral"] * 0.05:
            suggestions.append({
                "type": "TOKEN_REBALANCE",
                "token": token,
                "action": f"Reduce {'LONG' if net_exposure > 0 else 'SHORT'} exposure",
                "amount": f"${abs(net_exposure):,.2f}",
                "priority": "MEDIUM"
            })

    # 3. 지갑 분산 전략
    wallet_concentrations = []
    for wallet in total_stats["wallet_analysis"]:
        concentration = (wallet["total_collateral"] / total_stats["total_collateral"]) * 100
        if concentration > 15:  # 15% 이상 집중
            wallet_concentrations.append({
                "wallet": f"Wallet_{wallet['index']}",
                "concentration": f"{concentration:.1f}%"
            })

    if wallet_concentrations:
        suggestions.append({
            "type": "DIVERSIFICATION",
            "action": "Redistribute positions across more wallets",
            "details": wallet_concentrations,
            "priority": "MEDIUM"
        })

    # 4. 상관관계 은폐 전략
    suggestions.append({
        "type": "DECORRELATION",
        "action": "Vary position sizes, timing, and token selection across wallets",
        "details": [
            "Use different leverage levels for similar positions",
            "Stagger entry/exit times by several hours or days",
            "Mix different token pairs even for similar strategies",
            "Use varying position sizes (avoid round numbers)"
        ],
        "priority": "HIGH"
    })

    return suggestions

def print_analysis_report(total_stats: Dict[str, Any], correlation_metrics: Dict[str, Any], suggestions: List[Dict]):
    """분석 리포트 출력"""
    print("\n" + "="*80)
    print("PORTFOLIO ANALYSIS REPORT")
    print("="*80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print(f"\n📊 OVERALL STATISTICS")
    print(f"  Total Wallets: {total_stats['total_wallets']}")
    print(f"  Total Collateral: ${total_stats['total_collateral']:,.2f}")
    print(f"  Total PnL: ${total_stats['total_pnl']:,.2f}")
    print(f"  Total Long Exposure: ${total_stats['total_long']:,.2f}")
    print(f"  Total Short Exposure: ${total_stats['total_short']:,.2f}")
    print(f"  Net Delta: ${total_stats['total_net_delta']:,.2f}")
    print(f"  Delta Ratio (Long/Short): {total_stats['delta_ratio']:.2f}")

    print(f"\n📈 TOKEN EXPOSURE (Net)")
    for token, exposure in sorted(total_stats['net_exposure'].items(), key=lambda x: abs(x[1]), reverse=True):
        symbol = "🟢" if exposure > 0 else "🔴"
        print(f"  {symbol} {token}: ${exposure:,.2f}")

    print(f"\n👥 WALLET SUMMARY")
    for wallet in total_stats['wallet_analysis'][:5]:  # Top 5 wallets
        print(f"  Wallet {wallet['index']} ({wallet['address'][:10]}...)")
        print(f"    Balance: ${wallet['balance']:,.2f}")
        print(f"    Positions: {len(wallet['positions'])}")
        print(f"    Net Delta: ${wallet['net_delta']:,.2f}")
        print(f"    PnL: ${wallet['total_pnl']:,.2f}")

    if correlation_metrics['position_overlap']:
        print(f"\n🔗 CORRELATION ANALYSIS")
        print("  Position Overlaps Detected:")
        for pair, data in correlation_metrics['position_overlap'].items():
            print(f"    {pair}: {data['overlapping_positions']} positions (similarity: {data['similarity_score']:.1%})")

    print(f"\n💡 HEDGING RECOMMENDATIONS")
    for i, suggestion in enumerate(suggestions, 1):
        print(f"\n  {i}. [{suggestion['priority']}] {suggestion['type']}")
        print(f"     Action: {suggestion['action']}")
        if 'amount' in suggestion:
            print(f"     Amount: {suggestion['amount']}")
        if 'details' in suggestion and isinstance(suggestion['details'], list):
            if isinstance(suggestion['details'][0], dict):
                for detail in suggestion['details']:
                    print(f"     - {detail}")
            else:
                for detail in suggestion['details']:
                    print(f"     - {detail}")

    print("\n" + "="*80)

async def main():
    """메인 실행 함수"""
    # 지갑 주소 읽기
    with open("portfolio_analysis_wallets.txt", "r") as f:
        addresses = [line.strip() for line in f if line.strip()]

    print(f"Analyzing {len(addresses)} wallets...")

    async with aiohttp.ClientSession() as session:
        try:
            # 포트폴리오 데이터 가져오기
            portfolio_data = await fetch_portfolio(session, addresses)

            # 포지션 분석
            total_stats = analyze_positions(portfolio_data)

            # 상관관계 분석
            correlation_metrics = calculate_correlation_metrics(total_stats["wallet_analysis"])

            # 헷징 전략 제안
            suggestions = suggest_hedging_strategies(total_stats)

            # 리포트 출력
            print_analysis_report(total_stats, correlation_metrics, suggestions)

            # JSON 파일로 저장
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "total_stats": total_stats,
                "correlation_metrics": correlation_metrics,
                "suggestions": suggestions
            }

            with open("portfolio_analysis_report.json", "w") as f:
                json.dump(report_data, f, indent=2, default=str)

            print(f"\n📁 Detailed report saved to: portfolio_analysis_report.json")

        except Exception as e:
            print(f"Error analyzing portfolio: {e}")

if __name__ == "__main__":
    asyncio.run(main())