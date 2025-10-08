#!/usr/bin/env python3
import asyncio
import aiohttp
import json
import random
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict

# GROUP_A 지갑들
GROUP_A_WALLETS = [
    {"num": 9, "addr": "0x497506194d1Bc5D02597142D5A79D9198200118E"},   # 담보: $199.82
    {"num": 12, "addr": "0xa9B5be1fc07E0538A5278beedB3A45bb3fbDC893"},  # 담보: $102.96
    {"num": 13, "addr": "0x5979857213bb73233aDBf029a7454DFb00A33539"}, # 담보: $57.09
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

def analyze_current_positions(portfolio_data):
    """현재 포지션 분석"""

    wallet_data = {}
    group_exposure = defaultdict(float)

    for account in portfolio_data.get("accounts", []):
        address = account["l1_address"]
        wallet_num = next((w["num"] for w in GROUP_A_WALLETS if w["addr"] == address), 0)

        if wallet_num == 0:
            continue

        collateral = float(account.get("collateral", 0))
        positions = account.get("positions", [])

        current_positions = []
        used_margin = 0
        wallet_long = defaultdict(float)
        wallet_short = defaultdict(float)

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
                "margin": margin,
                "leverage": leverage
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
            "utilization_rate": (used_margin / max_margin * 100) if max_margin > 0 else 0
        }

    return wallet_data, dict(group_exposure)

def generate_volume_maximizing_orders(wallet_data, group_exposure, market_prices):
    """거래량 최대화 주문 생성"""

    rebalance_orders = []
    close_orders = []

    # 1단계: 기존 포지션 중 일부 청산하여 마진 확보
    for wallet_num, data in wallet_data.items():
        if data["utilization_rate"] > 80:  # 80% 이상 사용 중인 지갑
            # 가장 작은 포지션들을 청산 대상으로 선정
            positions_by_size = sorted(data["current_positions"], key=lambda x: x["exposure"])

            target_margin_to_free = data["collateral"] * 0.2  # 담보의 20%만큼 마진 확보
            freed_margin = 0

            for pos in positions_by_size:
                if freed_margin >= target_margin_to_free:
                    break

                close_orders.append({
                    "wallet_num": wallet_num,
                    "wallet_addr": data["address"],
                    "action": "CLOSE",
                    "token": pos["token"],
                    "side": pos["side"],
                    "current_exposure": pos["exposure"],
                    "margin_freed": pos["margin"],
                    "reason": "Free margin for volume maximization"
                })

                freed_margin += pos["margin"]
                data["available_margin"] += pos["margin"]  # 임시로 가용 마진 증가

    # 2단계: 그룹 내 델타 중립성을 유지하면서 새로운 포지션 생성
    # 각 토큰별 그룹 넷 익스포저 계산
    token_net_exposure = {}
    for token in NEW_PAIRS:
        long_exp = group_exposure.get(f"{token}_LONG", 0)
        short_exp = group_exposure.get(f"{token}_SHORT", 0)
        token_net_exposure[token] = long_exp - short_exp

    # 가용 마진이 많은 지갑부터 정렬
    available_wallets = sorted(
        [(num, data) for num, data in wallet_data.items() if data["available_margin"] > 15],
        key=lambda x: x[1]["available_margin"],
        reverse=True
    )

    # 각 지갑에 최대한 많은 포지션 할당
    used_tokens_per_wallet = defaultdict(set)

    for wallet_num, wallet_data_item in available_wallets:
        max_positions = min(4, len(NEW_PAIRS))  # 지갑당 최대 4개 포지션
        positions_created = 0

        # 사용 가능한 토큰들 (이미 해당 지갑에서 사용하지 않은 토큰)
        available_tokens = [t for t in NEW_PAIRS if t not in used_tokens_per_wallet[wallet_num]]
        random.shuffle(available_tokens)  # 랜덤 순서로 섞기

        for token in available_tokens:
            if positions_created >= max_positions:
                break

            if wallet_data_item["available_margin"] < 15:  # 최소 마진 체크
                break

            # 포지션 크기 결정 (가용 마진의 60% 사용, 3x 레버리지)
            position_margin = min(
                wallet_data_item["available_margin"] * 0.6,
                40  # 최대 40달러
            )

            if position_margin < 15:  # 최소 15달러
                continue

            # 사이드 결정: 그룹 넷 익스포저 기준으로 밸런싱
            net_exp = token_net_exposure.get(token, 0)

            # 넷 익스포저가 양수면 SHORT 추가, 음수면 LONG 추가
            if abs(net_exp) < 20:  # 작은 불균형이면 랜덤
                side = random.choice(["LONG", "SHORT"])
            elif net_exp > 0:
                side = "SHORT"
            else:
                side = "LONG"

            # 동일 토큰의 반대 포지션이 이미 있는지 체크
            has_opposite = any(
                pos["token"] == token and pos["side"] != side
                for pos in wallet_data_item["current_positions"]
            )

            if has_opposite:
                continue  # 동일 토큰의 반대 포지션이 있으면 스킵

            # 주문 생성
            notional = position_margin * 3  # 3x 레버리지

            rebalance_orders.append({
                "wallet_num": wallet_num,
                "wallet_addr": wallet_data_item["address"],
                "action": "OPEN",
                "token": token,
                "side": side,
                "margin": round(position_margin, 2),
                "leverage": 3,
                "notional": round(notional, 2),
                "reason": f"Volume maximization - {side} {token}"
            })

            # 업데이트
            wallet_data_item["available_margin"] -= position_margin
            used_tokens_per_wallet[wallet_num].add(token)

            # 그룹 익스포저 업데이트
            if side == "LONG":
                token_net_exposure[token] += notional
            else:
                token_net_exposure[token] -= notional

            positions_created += 1

    return close_orders, rebalance_orders

def calculate_volume_impact(close_orders, rebalance_orders):
    """거래량 영향 계산"""

    close_volume = sum(order["current_exposure"] for order in close_orders)
    new_volume = sum(order["notional"] for order in rebalance_orders)
    total_volume = close_volume + new_volume

    return {
        "close_volume": close_volume,
        "new_volume": new_volume,
        "total_volume": total_volume,
        "volume_multiplier": total_volume / max(close_volume, 1)  # 원래 거래량 대비 배수
    }

def print_volume_rebalance_report(wallet_data, close_orders, rebalance_orders, volume_impact):
    """거래량 리밸런싱 리포트 출력"""

    print("\n" + "="*80)
    print("🚀 GROUP_A VOLUME MAXIMIZATION REBALANCING")
    print("="*80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 전략 개요
    total_collateral = sum(data["collateral"] for data in wallet_data.values())
    total_available = sum(data["available_margin"] for data in wallet_data.values())

    print(f"\n📊 STRATEGY OVERVIEW:")
    print(f"    Target: Maximize trading volume while maintaining group balance")
    print(f"    Total Collateral: ${total_collateral:.2f}")
    print(f"    Available Margin: ${total_available:.2f}")
    print(f"    Close Orders: {len(close_orders)}")
    print(f"    New Orders: {len(rebalance_orders)}")

    # 거래량 분석
    print(f"\n📈 VOLUME IMPACT:")
    print(f"    Close Volume: ${volume_impact['close_volume']:10.2f}")
    print(f"    New Volume: ${volume_impact['new_volume']:12.2f}")
    print(f"    Total Volume: ${volume_impact['total_volume']:10.2f}")
    print(f"    Volume Multiplier: {volume_impact['volume_multiplier']:.1f}x")

    # 청산 주문
    if close_orders:
        print(f"\n🔸 STEP 1: POSITION CLOSURES (Free up margin)")
        print(f"-" * 60)

        for order in close_orders:
            print(f"    Close Wallet {order['wallet_num']:2} | {order['side']} {order['token']} | "
                  f"${order['current_exposure']:8.2f} | Margin freed: ${order['margin_freed']:6.2f}")

    # 신규 주문
    if rebalance_orders:
        print(f"\n🔸 STEP 2: NEW POSITIONS (Maximize volume)")
        print(f"-" * 60)

        total_new_margin = sum(order["margin"] for order in rebalance_orders)
        total_new_notional = sum(order["notional"] for order in rebalance_orders)

        print(f"    Total New Margin: ${total_new_margin:.2f}")
        print(f"    Total New Notional: ${total_new_notional:.2f}")

        for order in rebalance_orders:
            symbol = "🟢" if order["side"] == "LONG" else "🔴"
            print(f"    {symbol} Wallet {order['wallet_num']:2} | {order['side']} {order['token']} | "
                  f"Margin: ${order['margin']:6.2f} | Notional: ${order['notional']:8.2f}")

    # 실행 순서
    print(f"\n⚡ EXECUTION SEQUENCE:")
    print(f"-" * 60)
    print(f"    1. Execute all CLOSE orders first (free up margin)")
    print(f"    2. Wait 30 seconds between each close")
    print(f"    3. Execute NEW orders in parallel (3 wallets simultaneously)")
    print(f"    4. Monitor for slippage and adjust if needed")
    print(f"    5. Verify final group delta neutrality")

    if not close_orders and not rebalance_orders:
        print(f"\n❌ NO REBALANCING POSSIBLE:")
        print(f"    All wallets are already optimally positioned")
        print(f"    Consider increasing leverage or adding more capital")

async def main():
    """메인 실행"""

    print("🚀 Starting GROUP_A Volume Maximization...")

    # 데이터 조회
    print("📡 Fetching GROUP_A data...")
    portfolio_data, market_prices = await fetch_group_a_data()

    # 현재 상태 분석
    print("📊 Analyzing current positions...")
    wallet_data, group_exposure = analyze_current_positions(portfolio_data)

    # 거래량 최대화 주문 생성
    print("🎯 Generating volume maximization orders...")
    close_orders, rebalance_orders = generate_volume_maximizing_orders(
        wallet_data, group_exposure, market_prices
    )

    # 거래량 영향 계산
    volume_impact = calculate_volume_impact(close_orders, rebalance_orders)

    # 리포트 출력
    print_volume_rebalance_report(wallet_data, close_orders, rebalance_orders, volume_impact)

    # JSON 저장
    save_data = {
        "timestamp": datetime.now().isoformat(),
        "group": "GROUP_A",
        "strategy": "volume_maximization",
        "close_orders": close_orders,
        "rebalance_orders": rebalance_orders,
        "volume_impact": volume_impact,
        "summary": {
            "total_orders": len(close_orders) + len(rebalance_orders),
            "close_volume": volume_impact["close_volume"],
            "new_volume": volume_impact["new_volume"],
            "total_volume": volume_impact["total_volume"],
            "volume_multiplier": volume_impact["volume_multiplier"]
        }
    }

    with open("group_a_volume_rebalance.json", "w") as f:
        json.dump(save_data, f, indent=2)

    print(f"\n📁 Volume rebalancing strategy saved to: group_a_volume_rebalance.json")
    print(f"\n{'='*80}")

if __name__ == "__main__":
    asyncio.run(main())