#!/usr/bin/env python3
import asyncio
import aiohttp
import json
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict

# API endpoint
API_URL = "http://localhost:8000/api/fetch_accounts"

# 새로운 페어 목록
NEW_PAIRS = ["APEX", "STBL", "ZEC", "FF", "0G", "2Z", "EDEN"]

# 그룹 정의 (group_hedging_strategy.py 결과 기반)
GROUPS = {
    "GROUP_A": {
        "wallets": [
            "0x8b49af69dF8d44C735812D30A3A5c66BA6fc05Fc",  # Wallet 6
            "0xE81261c93c99b4DCE06068adC0C2a7fFE425732f",  # Wallet 7
            "0x51a35979C49354B2eD87F86eb1A679815753c331",  # Wallet 11
            "0x349f3e1db87719CE7c1013AE7b7Feb70053A1c2f",  # Wallet 8
        ],
        "focus_tokens": ["APEX", "STBL", "ZEC"],
        "priority": 1  # 즉시 실행 그룹
    },
    "GROUP_B": {
        "wallets": [
            "0x497506194d1Bc5D02597142D5A79D9198200118E",  # Wallet 9
            "0xFD930dB05F90885DEd7Db693057E5B899b528b2b",  # Wallet 15
            "0x5979857213bb73233aDBf029a7454DFb00A33539",  # Wallet 13
        ],
        "focus_tokens": ["ZEC", "FF", "EDEN"],
        "priority": 2
    },
    "GROUP_C": {
        "wallets": [
            "0x7878AE8C54227440293a0BB83b63F39DC24A0899",  # Wallet 3
            "0x9d1cA39386cb3D35c66674aA0Ce41e3403731241",  # Wallet 14
            "0x25dcd95A7a6D56eA4e781C7586306a4d9768227C",  # Wallet 10
            "0xC74Ef16B20c50B7337585a0a8e1eed3EDd50CF43",  # Wallet 1
            "0xe67b28750153E7D95Ff001b2557EbA6C5F56092c",  # Wallet 2
        ],
        "focus_tokens": ["0G", "2Z", "FF"],
        "priority": 3
    },
    "GROUP_D": {
        "wallets": [
            "0x29855eB076f6d4a571890a75fe8944380ca6ccC6",  # Wallet 5
            "0xa9B5be1fc07E0538A5278beedB3A45bb3fbDC893",  # Wallet 12
            "0x06d9681C02E2b5182C3489477f4b09D38f3959B2",  # Wallet 16
            "0xe5909A5817325797f8Ed2C4c079f6c78B5E9bfa2",  # Wallet 4
        ],
        "focus_tokens": ["EDEN", "STBL", "APEX"],
        "priority": 4
    }
}

async def fetch_current_positions(addresses: List[str]) -> Dict:
    """현재 포지션 조회"""
    async with aiohttp.ClientSession() as session:
        data = {"addresses": addresses}
        async with session.post(API_URL, json=data) as response:
            return await response.json()

async def fetch_market_prices() -> Dict:
    """현재 시장 가격 조회"""
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:8000/api/market_prices") as response:
            return await response.json()

def analyze_group_positions(group_name: str, portfolio_data: Dict, market_prices: Dict) -> Dict:
    """그룹별 포지션 분석 및 델타 계산"""

    group_info = GROUPS[group_name]
    group_wallets = group_info["wallets"]

    analysis = {
        "group_name": group_name,
        "wallets": [],
        "total_long_exposure": defaultdict(float),
        "total_short_exposure": defaultdict(float),
        "net_exposure": defaultdict(float),
        "current_positions": [],
        "rebalancing_needed": False,
        "urgency": "LOW"
    }

    # 각 지갑의 포지션 분석
    for account in portfolio_data.get("accounts", []):
        if account["l1_address"] in group_wallets:
            wallet_info = {
                "address": account["l1_address"],
                "balance": float(account.get("available_balance", 0)),
                "collateral": float(account.get("collateral", 0)),
                "positions": []
            }

            # 포지션이 있는 경우 분석
            for pos in account.get("positions", []):
                token = pos.get("symbol", "Unknown")  # symbol 필드 사용
                side = "LONG" if pos.get("sign", 1) == 1 else "SHORT"
                amount = float(pos.get("position", 0))  # position 필드 사용
                entry = float(pos.get("avg_entry_price", 0))  # avg_entry_price 필드 사용
                current = float(pos.get("current_price", entry))
                pnl = float(pos.get("unrealized_pnl", 0))
                pnl_percent = float(pos.get("liquidation_percent", 0))  # liquidation_percent로 대체

                # margin 계산 (position_value / leverage)
                position_value = float(pos.get("position_value", 0))
                leverage_str = pos.get("leverage", "3.0x")
                leverage = float(leverage_str.replace("x", ""))
                margin = position_value / leverage if leverage > 0 else 0

                # 노출도 계산 (현재가 * 수량)
                exposure = abs(amount * current)

                if side == "LONG":
                    analysis["total_long_exposure"][token] += exposure
                else:
                    analysis["total_short_exposure"][token] += exposure

                wallet_info["positions"].append({
                    "token": token,
                    "side": side,
                    "amount": amount,
                    "entry": entry,
                    "current": current,
                    "exposure": exposure,
                    "pnl": pnl,
                    "pnl_percent": pnl_percent,
                    "margin": margin
                })

                analysis["current_positions"].append({
                    "wallet": account["l1_address"][-6:],
                    "token": token,
                    "side": side,
                    "exposure": exposure,
                    "pnl_percent": pnl_percent
                })

            analysis["wallets"].append(wallet_info)

    # 넷 익스포저 계산
    all_tokens = set(list(analysis["total_long_exposure"].keys()) +
                     list(analysis["total_short_exposure"].keys()))

    total_imbalance = 0
    for token in all_tokens:
        long_exp = analysis["total_long_exposure"][token]
        short_exp = analysis["total_short_exposure"][token]
        net_exp = long_exp - short_exp
        analysis["net_exposure"][token] = net_exp
        total_imbalance += abs(net_exp)

    # 리밸런싱 필요 여부 판단
    if total_imbalance > 500:
        analysis["rebalancing_needed"] = True
        analysis["urgency"] = "HIGH"
    elif total_imbalance > 300:
        analysis["rebalancing_needed"] = True
        analysis["urgency"] = "MEDIUM"
    elif total_imbalance > 150:
        analysis["urgency"] = "MEDIUM"

    analysis["total_imbalance"] = total_imbalance
    analysis["delta_score"] = max(0, 100 - (total_imbalance / 10))

    return analysis

def generate_rebalancing_orders(analysis: Dict, market_prices: Dict) -> List[Dict]:
    """리밸런싱 주문 생성"""

    orders = []

    # 가장 불균형이 큰 토큰부터 처리
    sorted_exposures = sorted(
        analysis["net_exposure"].items(),
        key=lambda x: abs(x[1]),
        reverse=True
    )

    for token, net_exposure in sorted_exposures:
        if abs(net_exposure) < 50:  # 작은 불균형은 무시
            continue

        # 리밸런싱 방향 결정
        if net_exposure > 0:  # Long이 과다
            # Short 포지션 추가 또는 Long 포지션 축소
            action = "ADD_SHORT" if net_exposure > 200 else "REDUCE_LONG"
            target_amount = abs(net_exposure) * 0.5  # 50% 조정
        else:  # Short이 과다
            # Long 포지션 추가 또는 Short 포지션 축소
            action = "ADD_LONG" if abs(net_exposure) > 200 else "REDUCE_SHORT"
            target_amount = abs(net_exposure) * 0.5

        # 실행할 지갑 선택 (여유 마진이 있는 지갑)
        best_wallet = None
        max_available = 0

        for wallet in analysis["wallets"]:
            # 사용 가능한 마진 계산
            used_margin = sum(p["margin"] for p in wallet["positions"])
            available = wallet["collateral"] * 0.9 - used_margin

            if available > max_available:
                max_available = available
                best_wallet = wallet["address"]

        if best_wallet and max_available > 10:
            # 포지션 크기 계산 (3x 레버리지)
            position_size = min(target_amount / 3, max_available * 0.8)

            orders.append({
                "wallet": best_wallet,
                "token": token,
                "action": action,
                "side": "LONG" if "LONG" in action else "SHORT",
                "margin": round(position_size, 2),
                "leverage": 3,
                "notional": round(position_size * 3, 2),
                "reason": f"Rebalance {token} (net: ${net_exposure:.2f})",
                "urgency": analysis["urgency"]
            })

    return orders

def print_analysis_report(analyses: Dict, priority_group: str = None):
    """분석 리포트 출력"""

    print("\n" + "="*80)
    print("IMMEDIATE REBALANCING ANALYSIS")
    print("="*80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 우선순위 그룹 결정
    if not priority_group:
        # 가장 불균형이 큰 그룹 선택
        priority_group = max(
            analyses.keys(),
            key=lambda x: analyses[x]["total_imbalance"]
        )

    print(f"\n🎯 PRIORITY GROUP: {priority_group}")

    # 각 그룹 요약
    print("\n📊 GROUP SUMMARY")
    for group_name in ["GROUP_A", "GROUP_B", "GROUP_C", "GROUP_D"]:
        if group_name not in analyses:
            continue

        analysis = analyses[group_name]
        status = "🔴" if analysis["rebalancing_needed"] else "🟢"
        print(f"\n  {group_name}:")
        print(f"    Status: {status} {analysis['urgency']}")
        print(f"    Delta Score: {analysis['delta_score']:.1f}/100")
        print(f"    Total Imbalance: ${analysis['total_imbalance']:.2f}")

        # 주요 불균형
        if analysis["net_exposure"]:
            print(f"    Main Imbalances:")
            for token, net in sorted(
                analysis["net_exposure"].items(),
                key=lambda x: abs(x[1]),
                reverse=True
            )[:3]:
                if abs(net) > 10:
                    symbol = "L+" if net > 0 else "S+"
                    print(f"      {token}: {symbol} ${abs(net):.2f}")

    # 우선순위 그룹 상세
    priority_analysis = analyses[priority_group]
    print(f"\n{'='*40}")
    print(f"📋 {priority_group} DETAILED ANALYSIS")
    print(f"{'='*40}")

    print("\n  Current Positions:")
    for pos in priority_analysis["current_positions"][:10]:
        symbol = "🟢" if pos["side"] == "LONG" else "🔴"
        pnl_symbol = "+" if pos["pnl_percent"] > 0 else ""
        print(f"    {symbol} ...{pos['wallet']}: {pos['side']} {pos['token']} "
              f"(${pos['exposure']:.2f}, {pnl_symbol}{pos['pnl_percent']:.1f}%)")

    print("\n  Net Exposures:")
    for token, net in sorted(
        priority_analysis["net_exposure"].items(),
        key=lambda x: abs(x[1]),
        reverse=True
    ):
        if abs(net) > 10:
            long = priority_analysis["total_long_exposure"].get(token, 0)
            short = priority_analysis["total_short_exposure"].get(token, 0)
            symbol = "🟢" if net > 0 else "🔴"
            print(f"    {symbol} {token}: ${net:+.2f} (L:${long:.0f}/S:${short:.0f})")

def print_rebalancing_orders(orders: List[Dict], group_name: str):
    """리밸런싱 주문 출력"""

    if not orders:
        print(f"\n✅ {group_name}: No rebalancing needed")
        return

    print(f"\n{'='*40}")
    print(f"📝 REBALANCING ORDERS FOR {group_name}")
    print(f"{'='*40}")

    total_margin = sum(o["margin"] for o in orders)
    total_notional = sum(o["notional"] for o in orders)

    print(f"\n  Summary:")
    print(f"    Total Orders: {len(orders)}")
    print(f"    Total Margin Required: ${total_margin:.2f}")
    print(f"    Total Notional Volume: ${total_notional:.2f}")

    print(f"\n  Orders to Execute:")
    for i, order in enumerate(orders, 1):
        print(f"\n    Order {i}:")
        print(f"      Wallet: ...{order['wallet'][-6:]}")
        print(f"      Action: {order['action']} {order['token']}")
        print(f"      Size: ${order['margin']:.2f} @ {order['leverage']}x")
        print(f"      Notional: ${order['notional']:.2f}")
        print(f"      Reason: {order['reason']}")

    print(f"\n  Execution Steps:")
    print(f"    1. Check market conditions for slippage")
    print(f"    2. Execute orders in sequence with 30s gaps")
    print(f"    3. Verify positions after each order")
    print(f"    4. Stop if delta improves to acceptable level")

async def main():
    """메인 실행 함수"""

    print("Fetching current positions and market data...")

    # 모든 지갑 주소 수집
    all_addresses = []
    for group in GROUPS.values():
        all_addresses.extend(group["wallets"])

    # 현재 포지션과 시장 가격 조회
    portfolio_data = await fetch_current_positions(all_addresses)
    market_prices = await fetch_market_prices()

    # 각 그룹 분석
    analyses = {}
    for group_name in GROUPS.keys():
        analyses[group_name] = analyze_group_positions(
            group_name,
            portfolio_data,
            market_prices
        )

    # 분석 리포트 출력
    print_analysis_report(analyses)

    # 가장 급한 그룹 선택
    priority_group = max(
        analyses.keys(),
        key=lambda x: (
            analyses[x]["total_imbalance"]
            if analyses[x]["urgency"] == "HIGH"
            else 0
        )
    )

    # 리밸런싱 주문 생성
    priority_analysis = analyses[priority_group]

    if priority_analysis["rebalancing_needed"]:
        orders = generate_rebalancing_orders(priority_analysis, market_prices)
        print_rebalancing_orders(orders, priority_group)

        # JSON 파일로 저장
        save_data = {
            "timestamp": datetime.now().isoformat(),
            "priority_group": priority_group,
            "analysis": {
                "delta_score": priority_analysis["delta_score"],
                "total_imbalance": priority_analysis["total_imbalance"],
                "net_exposure": dict(priority_analysis["net_exposure"])
            },
            "orders": orders
        }

        with open("immediate_rebalance_orders.json", "w") as f:
            json.dump(save_data, f, indent=2)

        print(f"\n📁 Orders saved to: immediate_rebalance_orders.json")
    else:
        print(f"\n✅ All groups are within acceptable delta ranges")

    print("\n" + "="*80)

if __name__ == "__main__":
    asyncio.run(main())