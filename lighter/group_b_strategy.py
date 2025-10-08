#!/usr/bin/env python3
import asyncio
import aiohttp
import json
import random
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict

# GROUP_B 지갑들 (최적화된 분할 결과)
GROUP_B_WALLETS = [
    {"num": 6, "addr": "0x8b49af69dF8d44C735812D30A3A5c66BA6fc05Fc"},   # 담보: $197.25
    {"num": 11, "addr": "0x51a35979C49354B2eD87F86eb1A679815753c331"},  # 담보: $34.38
    {"num": 2, "addr": "0xe67b28750153E7D95Ff001b2557EbA6C5F56092c"},   # 담보: $20.75
    {"num": 4, "addr": "0xe5909A5817325797f8Ed2C4c079f6c78B5E9bfa2"},   # 담보: $5.16
    {"num": 15, "addr": "0xFD930dB05F90885DEd7Db693057E5B899b528b2b"},  # 담보: $107.75
]

NEW_PAIRS = ["APEX", "STBL", "ZEC", "FF", "0G", "2Z", "EDEN"]

async def fetch_group_b_data():
    """GROUP_B 지갑 데이터 조회"""
    addresses = [w["addr"] for w in GROUP_B_WALLETS]

    async with aiohttp.ClientSession() as session:
        data = {"addresses": addresses}
        async with session.post("http://localhost:8000/api/fetch_accounts", json=data) as response:
            portfolio_data = await response.json()

        async with session.get("http://localhost:8000/api/market_prices") as response:
            market_prices = await response.json()

    return portfolio_data, market_prices

def analyze_group_b_positions(portfolio_data):
    """GROUP_B 현재 포지션 분석"""

    wallet_data = {}
    group_exposure = defaultdict(float)

    for account in portfolio_data.get("accounts", []):
        address = account["l1_address"]
        wallet_num = next((w["num"] for w in GROUP_B_WALLETS if w["addr"] == address), 0)

        if wallet_num == 0:
            continue

        collateral = float(account.get("collateral", 0))
        positions = account.get("positions", [])

        current_positions = []
        used_margin = 0
        wallet_long = defaultdict(float)
        wallet_short = defaultdict(float)
        total_exposure = 0

        for pos in positions:
            token = pos.get("symbol", "Unknown")
            side = "LONG" if pos.get("sign", 1) == 1 else "SHORT"
            amount = float(pos.get("position", 0))
            current_price = float(pos.get("current_price", 0))
            exposure = abs(amount * current_price)
            total_exposure += exposure

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
                "margin": margin,
                "leverage": leverage,
                "pnl": float(pos.get("unrealized_pnl", 0))
            })

            # 그룹 전체 익스포저 계산
            if side == "LONG":
                wallet_long[token] += exposure
                group_exposure[f"{token}_LONG"] += exposure
            else:
                wallet_short[token] += exposure
                group_exposure[f"{token}_SHORT"] += exposure

        # 가용 마진 계산
        max_margin = collateral * 0.9
        available_margin = max(0, max_margin - used_margin)

        wallet_data[wallet_num] = {
            "address": address,
            "collateral": collateral,
            "used_margin": used_margin,
            "available_margin": available_margin,
            "max_margin": max_margin,
            "current_positions": current_positions,
            "wallet_long": dict(wallet_long),
            "wallet_short": dict(wallet_short),
            "total_exposure": total_exposure,
            "utilization_rate": (used_margin / max_margin * 100) if max_margin > 0 else 0
        }

    return wallet_data, dict(group_exposure)

def generate_group_b_strategy(wallet_data, group_exposure, market_prices):
    """GROUP_B 전략 생성"""

    strategy_orders = []
    close_orders = []

    # GROUP_B 특성 분석
    # - 총 담보: $365.29 (가장 큰 그룹)
    # - 5개 지갑으로 다양성 높음
    # - 델타 bias: +0.22 (롱 성향)

    print(f"\n📊 GROUP_B ANALYSIS:")
    total_collateral = sum(data["collateral"] for data in wallet_data.values())
    total_available = sum(data["available_margin"] for data in wallet_data.values())
    print(f"    Total Collateral: ${total_collateral:.2f}")
    print(f"    Total Available: ${total_available:.2f}")

    # 각 지갑별 상태 출력
    for wallet_num in sorted(wallet_data.keys()):
        data = wallet_data[wallet_num]
        print(f"    Wallet {wallet_num:2} | Collateral: ${data['collateral']:8.2f} | "
              f"Available: ${data['available_margin']:7.2f} | "
              f"Utilization: {data['utilization_rate']:5.1f}%")

    # 전략 1: 과도하게 활용된 지갑의 작은 포지션 청산
    high_util_wallets = [
        (num, data) for num, data in wallet_data.items()
        if data["utilization_rate"] > 85 and data["current_positions"]
    ]

    for wallet_num, data in high_util_wallets:
        # 가장 작은 포지션 2개 청산
        positions_by_size = sorted(data["current_positions"], key=lambda x: x["exposure"])

        target_free_margin = data["collateral"] * 0.25  # 담보의 25% 확보
        freed_margin = 0

        for pos in positions_by_size[:2]:  # 최대 2개까지
            if freed_margin >= target_free_margin:
                break

            close_orders.append({
                "wallet_num": wallet_num,
                "wallet_addr": data["address"],
                "action": "CLOSE",
                "token": pos["token"],
                "side": pos["side"],
                "current_exposure": pos["exposure"],
                "margin_freed": pos["margin"],
                "pnl": pos["pnl"],
                "reason": f"Free margin for GROUP_B optimization"
            })

            freed_margin += pos["margin"]
            data["available_margin"] += pos["margin"]  # 임시 업데이트

    # 전략 2: 가용 마진이 있는 지갑에 새로운 포지션 배치
    available_wallets = [
        (num, data) for num, data in wallet_data.items()
        if data["available_margin"] > 12
    ]

    # 그룹 델타 중립성을 고려한 토큰별 넷 포지션 계산
    token_net_exposure = {}
    for token in NEW_PAIRS:
        long_exp = group_exposure.get(f"{token}_LONG", 0)
        short_exp = group_exposure.get(f"{token}_SHORT", 0)
        token_net_exposure[token] = long_exp - short_exp

    # 가용 마진 순으로 정렬
    available_wallets.sort(key=lambda x: x[1]["available_margin"], reverse=True)

    # 각 지갑에 최적 포지션 할당
    for wallet_num, wallet_data_item in available_wallets:
        if wallet_data_item["available_margin"] < 12:
            continue

        # 지갑 크기에 따른 포지션 수 결정
        if wallet_data_item["collateral"] > 150:  # 큰 지갑
            max_new_positions = 3
        elif wallet_data_item["collateral"] > 50:   # 중간 지갑
            max_new_positions = 2
        else:  # 작은 지갑
            max_new_positions = 1

        positions_created = 0
        used_tokens = set(pos["token"] for pos in wallet_data_item["current_positions"])

        # 사용 가능한 토큰 선택
        available_tokens = [t for t in NEW_PAIRS if t not in used_tokens]

        # 델타 균형을 위한 토큰 우선순위
        tokens_by_imbalance = sorted(
            available_tokens,
            key=lambda t: abs(token_net_exposure.get(t, 0)),
            reverse=True
        )

        for token in tokens_by_imbalance:
            if positions_created >= max_new_positions:
                break

            if wallet_data_item["available_margin"] < 12:
                break

            # 포지션 크기 결정
            position_margin = min(
                wallet_data_item["available_margin"] * 0.7,  # 가용 마진의 70%
                35  # 최대 35달러
            )

            if position_margin < 12:  # 최소 12달러
                continue

            # 사이드 결정: 넷 익스포저 기준
            net_exp = token_net_exposure.get(token, 0)

            if abs(net_exp) < 30:  # 작은 불균형
                # 그룹의 전반적인 롱 bias를 고려하여 숏 성향으로
                side = "SHORT" if random.random() > 0.3 else "LONG"
            elif net_exp > 0:  # 롱이 많음
                side = "SHORT"
            else:  # 숏이 많음
                side = "LONG"

            # 동일 토큰 반대 포지션 체크
            has_opposite = any(
                pos["token"] == token and pos["side"] != side
                for pos in wallet_data_item["current_positions"]
            )

            if has_opposite:
                continue

            notional = position_margin * 3  # 3x 레버리지

            strategy_orders.append({
                "wallet_num": wallet_num,
                "wallet_addr": wallet_data_item["address"],
                "action": "OPEN",
                "token": token,
                "side": side,
                "margin": round(position_margin, 2),
                "leverage": 3,
                "notional": round(notional, 2),
                "reason": f"GROUP_B optimization - balance {token}"
            })

            # 업데이트
            wallet_data_item["available_margin"] -= position_margin
            if side == "LONG":
                token_net_exposure[token] += notional
            else:
                token_net_exposure[token] -= notional

            positions_created += 1

    return close_orders, strategy_orders

def calculate_group_b_impact(wallet_data, close_orders, strategy_orders):
    """GROUP_B 전략 영향 계산"""

    # 현재 그룹 상태
    current_total_exposure = sum(data["total_exposure"] for data in wallet_data.values())
    current_total_margin = sum(data["used_margin"] for data in wallet_data.values())

    # 거래량 계산
    close_volume = sum(order["current_exposure"] for order in close_orders)
    new_volume = sum(order["notional"] for order in strategy_orders)
    total_volume = close_volume + new_volume

    # 마진 변화
    margin_freed = sum(order["margin_freed"] for order in close_orders)
    margin_used = sum(order["margin"] for order in strategy_orders)
    net_margin_change = margin_used - margin_freed

    return {
        "current_exposure": current_total_exposure,
        "close_volume": close_volume,
        "new_volume": new_volume,
        "total_volume": total_volume,
        "margin_freed": margin_freed,
        "margin_used": margin_used,
        "net_margin_change": net_margin_change,
        "volume_increase": new_volume - close_volume,
        "efficiency_ratio": new_volume / margin_used if margin_used > 0 else 0
    }

def print_group_b_report(wallet_data, close_orders, strategy_orders, impact):
    """GROUP_B 리포트 출력"""

    print("\n" + "="*80)
    print("🎯 GROUP_B OPTIMIZATION STRATEGY")
    print("="*80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 전략 개요
    total_collateral = sum(data["collateral"] for data in wallet_data.values())

    print(f"\n📊 GROUP_B OVERVIEW:")
    print(f"    Strategy: Balanced optimization with delta control")
    print(f"    Total Collateral: ${total_collateral:.2f}")
    print(f"    Wallets: {len(wallet_data)} (largest group)")
    print(f"    Close Orders: {len(close_orders)}")
    print(f"    New Orders: {len(strategy_orders)}")

    # 영향 분석
    print(f"\n📈 STRATEGY IMPACT:")
    print(f"    Current Exposure: ${impact['current_exposure']:10.2f}")
    print(f"    Close Volume: ${impact['close_volume']:14.2f}")
    print(f"    New Volume: ${impact['new_volume']:16.2f}")
    print(f"    Net Volume Change: ${impact['volume_increase']:+8.2f}")
    print(f"    Margin Efficiency: {impact['efficiency_ratio']:.1f}x")

    # 청산 주문
    if close_orders:
        print(f"\n🔸 POSITION CLOSURES:")
        print(f"-" * 60)

        total_pnl = sum(order["pnl"] for order in close_orders)
        print(f"    Total Positions to Close: {len(close_orders)}")
        print(f"    Total PnL Impact: ${total_pnl:+.2f}")

        for order in close_orders:
            pnl_symbol = "+" if order["pnl"] > 0 else ""
            print(f"    Close Wallet {order['wallet_num']:2} | {order['side']} {order['token']} | "
                  f"${order['current_exposure']:8.2f} | PnL: {pnl_symbol}${order['pnl']:6.2f}")

    # 신규 주문
    if strategy_orders:
        print(f"\n🔸 NEW POSITIONS:")
        print(f"-" * 60)

        total_new_margin = sum(order["margin"] for order in strategy_orders)
        total_new_notional = sum(order["notional"] for order in strategy_orders)

        print(f"    Total New Positions: {len(strategy_orders)}")
        print(f"    Total Margin Required: ${total_new_margin:.2f}")
        print(f"    Total Notional: ${total_new_notional:.2f}")

        for order in strategy_orders:
            symbol = "🟢" if order["side"] == "LONG" else "🔴"
            print(f"    {symbol} Wallet {order['wallet_num']:2} | {order['side']} {order['token']} | "
                  f"Margin: ${order['margin']:6.2f} | Notional: ${order['notional']:8.2f}")

    # 실행 지침
    print(f"\n⚡ EXECUTION PLAN:")
    print(f"-" * 60)
    print(f"    Phase 1: Execute CLOSE orders (free up margin)")
    print(f"    Phase 2: Wait 60 seconds for settlement")
    print(f"    Phase 3: Execute NEW orders in order of wallet size")
    print(f"    Phase 4: Monitor group delta and adjust if needed")

    if not close_orders and not strategy_orders:
        print(f"\n✅ GROUP_B ALREADY OPTIMIZED:")
        print(f"    All wallets are efficiently positioned")
        print(f"    Consider inter-group rebalancing instead")

async def main():
    """메인 실행"""

    print("🚀 Starting GROUP_B Strategy Analysis...")

    # 데이터 조회
    print("📡 Fetching GROUP_B data...")
    portfolio_data, market_prices = await fetch_group_b_data()

    # 포지션 분석
    print("📊 Analyzing GROUP_B positions...")
    wallet_data, group_exposure = analyze_group_b_positions(portfolio_data)

    # 전략 생성
    print("🎯 Generating GROUP_B strategy...")
    close_orders, strategy_orders = generate_group_b_strategy(
        wallet_data, group_exposure, market_prices
    )

    # 영향 계산
    impact = calculate_group_b_impact(wallet_data, close_orders, strategy_orders)

    # 리포트 출력
    print_group_b_report(wallet_data, close_orders, strategy_orders, impact)

    # JSON 저장
    save_data = {
        "timestamp": datetime.now().isoformat(),
        "group": "GROUP_B",
        "strategy": "balanced_optimization",
        "wallet_analysis": {str(k): v for k, v in wallet_data.items()},
        "close_orders": close_orders,
        "strategy_orders": strategy_orders,
        "impact_analysis": impact,
        "summary": {
            "total_orders": len(close_orders) + len(strategy_orders),
            "net_volume_change": impact["volume_increase"],
            "efficiency_ratio": impact["efficiency_ratio"],
            "group_size": len(wallet_data)
        }
    }

    with open("group_b_strategy.json", "w") as f:
        json.dump(save_data, f, indent=2)

    print(f"\n📁 GROUP_B strategy saved to: group_b_strategy.json")
    print(f"\n{'='*80}")

if __name__ == "__main__":
    asyncio.run(main())