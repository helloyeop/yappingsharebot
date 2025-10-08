#!/usr/bin/env python3
import asyncio
import aiohttp
import json
import random
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict

# GROUP_A 지갑들 (최적화된 분할 결과)
GROUP_A_WALLETS = [
    {"num": 9, "addr": "0x497506194d1Bc5D02597142D5A79D9198200118E"},   # 담보: $199.82, 가용: $21.93
    {"num": 12, "addr": "0xa9B5be1fc07E0538A5278beedB3A45bb3fbDC893"},  # 담보: $102.96, 가용: $12.01
    {"num": 13, "addr": "0x5979857213bb73233aDBf029a7454DFb00A33539"}, # 담보: $57.09, 가용: $4.80
]

NEW_PAIRS = ["APEX", "STBL", "ZEC", "FF", "0G", "2Z", "EDEN"]

async def fetch_group_a_data():
    """GROUP_A 지갑 데이터 조회"""
    addresses = [w["addr"] for w in GROUP_A_WALLETS]

    async with aiohttp.ClientSession() as session:
        data = {"addresses": addresses}
        async with session.post("http://localhost:8000/api/fetch_accounts", json=data) as response:
            portfolio_data = await response.json()

        async with session.get("http://localhost:8000/api/market_prices") as response:
            market_prices = await response.json()

    return portfolio_data, market_prices

def analyze_group_a_current_state(portfolio_data):
    """GROUP_A 현재 상태 분석"""

    wallet_analysis = {}

    for account in portfolio_data.get("accounts", []):
        address = account["l1_address"]
        wallet_num = next((w["num"] for w in GROUP_A_WALLETS if w["addr"] == address), 0)

        if wallet_num == 0:
            continue

        collateral = float(account.get("collateral", 0))
        positions = account.get("positions", [])

        # 현재 포지션 분석
        current_positions = []
        used_margin = 0
        token_exposure = defaultdict(float)
        long_exposure = 0
        short_exposure = 0

        for pos in positions:
            token = pos.get("symbol", "Unknown")
            side = "LONG" if pos.get("sign", 1) == 1 else "SHORT"
            amount = float(pos.get("position", 0))
            current_price = float(pos.get("current_price", 0))
            exposure = abs(amount * current_price)

            # 마진 계산
            position_value = float(pos.get("position_value", 0))
            leverage_str = pos.get("leverage", "3.0x")
            leverage = float(leverage_str.replace("x", ""))
            margin = position_value / leverage if leverage > 0 else 0
            used_margin += margin

            current_positions.append({
                "token": token,
                "side": side,
                "amount": amount,
                "exposure": exposure,
                "margin": margin
            })

            token_exposure[token] += exposure
            if side == "LONG":
                long_exposure += exposure
            else:
                short_exposure += exposure

        # 가용 마진 계산
        max_margin = collateral * 0.9
        available_margin = max(0, max_margin - used_margin)

        wallet_analysis[wallet_num] = {
            "address": address,
            "collateral": collateral,
            "used_margin": used_margin,
            "available_margin": available_margin,
            "current_positions": current_positions,
            "token_exposure": dict(token_exposure),
            "long_exposure": long_exposure,
            "short_exposure": short_exposure,
            "delta_bias": (long_exposure - short_exposure) / (long_exposure + short_exposure) if (long_exposure + short_exposure) > 0 else 0
        }

    return wallet_analysis

def generate_group_a_hedging_strategy(wallet_analysis, market_prices):
    """GROUP_A 헷징 전략 생성"""

    hedge_orders = []

    # 사용 가능한 지갑 (가용 마진 > 10)
    available_wallets = [
        (num, analysis) for num, analysis in wallet_analysis.items()
        if analysis["available_margin"] > 10
    ]

    if len(available_wallets) < 2:
        return []

    # 가용 마진 순으로 정렬
    available_wallets.sort(key=lambda x: x[1]["available_margin"], reverse=True)

    # 각 토큰에 대해 헷징 페어 생성
    used_wallets = set()

    for token in NEW_PAIRS[:3]:  # 상위 3개 토큰만 사용
        if len(available_wallets) - len(used_wallets) < 2:
            break

        # 아직 사용되지 않은 지갑 2개 선택
        unused_wallets = [(num, analysis) for num, analysis in available_wallets if num not in used_wallets]

        if len(unused_wallets) < 2:
            break

        wallet_1 = unused_wallets[0]
        wallet_2 = unused_wallets[1]

        # 포지션 크기 결정 (작은 쪽 가용 마진 기준)
        min_available = min(wallet_1[1]["available_margin"], wallet_2[1]["available_margin"])
        position_margin = min(min_available * 0.8, 30)  # 최대 30달러

        if position_margin >= 10:  # 최소 10달러
            # 델타 bias를 고려한 사이드 배정
            wallet_1_bias = wallet_1[1]["delta_bias"]
            wallet_2_bias = wallet_2[1]["delta_bias"]

            # bias가 높은 지갑에 SHORT, 낮은 지갑에 LONG
            if wallet_1_bias > wallet_2_bias:
                long_wallet, short_wallet = wallet_2, wallet_1
            else:
                long_wallet, short_wallet = wallet_1, wallet_2

            # LONG 포지션
            hedge_orders.append({
                "wallet_num": long_wallet[0],
                "wallet_addr": long_wallet[1]["address"],
                "token": token,
                "side": "LONG",
                "margin": round(position_margin, 2),
                "leverage": 3,
                "notional": round(position_margin * 3, 2),
                "pair_id": f"{token}_HEDGE",
                "hedge_partner": short_wallet[0],
                "reason": f"GROUP_A hedging pair for {token}"
            })

            # SHORT 포지션 (헷지)
            hedge_orders.append({
                "wallet_num": short_wallet[0],
                "wallet_addr": short_wallet[1]["address"],
                "token": token,
                "side": "SHORT",
                "margin": round(position_margin, 2),
                "leverage": 3,
                "notional": round(position_margin * 3, 2),
                "pair_id": f"{token}_HEDGE",
                "hedge_partner": long_wallet[0],
                "reason": f"GROUP_A hedging pair for {token}"
            })

            # 사용된 지갑 표시
            used_wallets.add(long_wallet[0])
            used_wallets.add(short_wallet[0])

            # 가용 마진 업데이트
            wallet_analysis[long_wallet[0]]["available_margin"] -= position_margin
            wallet_analysis[short_wallet[0]]["available_margin"] -= position_margin

    return hedge_orders

def calculate_group_a_delta(wallet_analysis, hedge_orders):
    """GROUP_A 델타 중립성 계산"""

    # 현재 익스포저
    current_long = sum(w["long_exposure"] for w in wallet_analysis.values())
    current_short = sum(w["short_exposure"] for w in wallet_analysis.values())

    # 새로운 포지션 익스포저
    new_long = sum(o["notional"] for o in hedge_orders if o["side"] == "LONG")
    new_short = sum(o["notional"] for o in hedge_orders if o["side"] == "SHORT")

    # 총 익스포저
    total_long = current_long + new_long
    total_short = current_short + new_short
    total_exposure = total_long + total_short

    delta = (total_long - total_short) / total_exposure if total_exposure > 0 else 0
    delta_score = max(0, 100 - abs(delta) * 100)

    return {
        "current_long": current_long,
        "current_short": current_short,
        "new_long": new_long,
        "new_short": new_short,
        "total_long": total_long,
        "total_short": total_short,
        "delta": delta,
        "delta_score": delta_score
    }

def print_group_a_report(wallet_analysis, hedge_orders, delta_analysis):
    """GROUP_A 리포트 출력"""

    print("\n" + "="*80)
    print("🎯 GROUP_A INTRA-HEDGING STRATEGY")
    print("="*80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 그룹 개요
    total_collateral = sum(w["collateral"] for w in wallet_analysis.values())
    total_available = sum(w["available_margin"] for w in wallet_analysis.values())
    total_margin_needed = sum(o["margin"] for o in hedge_orders)

    print(f"\n📊 GROUP_A OVERVIEW:")
    print(f"    Wallets: {len(wallet_analysis)}")
    print(f"    Total Collateral: ${total_collateral:.2f}")
    print(f"    Available Margin: ${total_available:.2f}")
    print(f"    Hedge Orders: {len(hedge_orders)}")
    print(f"    Margin Required: ${total_margin_needed:.2f}")

    # 현재 포지션 상태
    print(f"\n💰 CURRENT WALLET STATUS:")
    for wallet_num in sorted(wallet_analysis.keys()):
        analysis = wallet_analysis[wallet_num]
        print(f"\n    Wallet {wallet_num} (...{analysis['address'][-6:]}):")
        print(f"      Collateral: ${analysis['collateral']:8.2f}")
        print(f"      Available: ${analysis['available_margin']:9.2f}")
        print(f"      Delta Bias: {analysis['delta_bias']:+7.2f}")

        if analysis["current_positions"]:
            print(f"      Current Positions:")
            for pos in analysis["current_positions"]:
                symbol = "🟢" if pos["side"] == "LONG" else "🔴"
                print(f"        {symbol} {pos['side']} {pos['token']} | ${pos['exposure']:.2f}")

    # 헷징 주문
    if hedge_orders:
        print(f"\n🔗 HEDGING PAIRS TO EXECUTE:")

        # 페어별로 그룹핑
        pairs = defaultdict(list)
        for order in hedge_orders:
            pairs[order["pair_id"]].append(order)

        for pair_id, pair_orders in pairs.items():
            token = pair_id.replace("_HEDGE", "")
            print(f"\n    💎 {token} Hedge Pair:")

            for order in pair_orders:
                symbol = "🟢" if order["side"] == "LONG" else "🔴"
                print(f"      {symbol} Wallet {order['wallet_num']:2} | {order['side']} {order['token']} | "
                      f"Margin: ${order['margin']:.2f} | Notional: ${order['notional']:.2f}")

    # 델타 분석
    print(f"\n⚖️ DELTA ANALYSIS:")
    print(f"    Current Delta: {delta_analysis['delta']:+.3f}")
    print(f"    Delta Score: {delta_analysis['delta_score']:.1f}/100")
    print(f"    Current Long: ${delta_analysis['current_long']:.2f}")
    print(f"    Current Short: ${delta_analysis['current_short']:.2f}")
    print(f"    New Long: ${delta_analysis['new_long']:.2f}")
    print(f"    New Short: ${delta_analysis['new_short']:.2f}")

    if not hedge_orders:
        print(f"\n❌ NO HEDGING POSSIBLE:")
        print(f"    Insufficient available margin in GROUP_A wallets")
        print(f"    Consider rebalancing existing positions first")

async def main():
    """메인 실행 - GROUP_A 전용"""

    print("🚀 Starting GROUP_A Intra-Hedging Strategy...")

    # GROUP_A 데이터 조회
    print("📡 Fetching GROUP_A wallet data...")
    portfolio_data, market_prices = await fetch_group_a_data()

    # 현재 상태 분석
    print("📊 Analyzing current positions...")
    wallet_analysis = analyze_group_a_current_state(portfolio_data)

    # 헷징 전략 생성
    print("🎯 Generating hedging strategy...")
    hedge_orders = generate_group_a_hedging_strategy(wallet_analysis, market_prices)

    # 델타 분석
    delta_analysis = calculate_group_a_delta(wallet_analysis, hedge_orders)

    # 리포트 출력
    print_group_a_report(wallet_analysis, hedge_orders, delta_analysis)

    # JSON 저장
    save_data = {
        "timestamp": datetime.now().isoformat(),
        "group": "GROUP_A",
        "wallet_analysis": {
            str(k): v for k, v in wallet_analysis.items()
        },
        "hedge_orders": hedge_orders,
        "delta_analysis": delta_analysis,
        "summary": {
            "total_hedges": len(hedge_orders),
            "total_margin": sum(o["margin"] for o in hedge_orders),
            "total_notional": sum(o["notional"] for o in hedge_orders),
            "final_delta_score": delta_analysis["delta_score"]
        }
    }

    with open("group_a_strategy.json", "w") as f:
        json.dump(save_data, f, indent=2)

    print(f"\n📁 GROUP_A strategy saved to: group_a_strategy.json")
    print(f"\n{'='*80}")

if __name__ == "__main__":
    asyncio.run(main())