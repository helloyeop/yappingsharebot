#!/usr/bin/env python3
import asyncio
import aiohttp
import json
import random
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict

# 17개 지갑을 4개 그룹으로 분할
WALLET_GROUPS = {
    "GROUP_A": [
        "0xC74Ef16B20c50B7337585a0a8e1eed3EDd50CF43",  # Wallet 1
        "0xe67b28750153E7D95Ff001b2557EbA6C5F56092c",  # Wallet 2
        "0x7878AE8C54227440293a0BB83b63F39DC24A0899",  # Wallet 3
        "0xe5909A5817325797f8Ed2C4c079f6c78B5E9bfa2",  # Wallet 4
        "0x29855eB076f6d4a571890a75fe8944380ca6ccC6",  # Wallet 5
    ],
    "GROUP_B": [
        "0x8b49af69dF8d44C735812D30A3A5c66BA6fc05Fc",  # Wallet 6
        "0xE81261c93c99b4DCE06068adC0C2a7fFE425732f",  # Wallet 7
        "0x349f3e1db87719CE7c1013AE7b7Feb70053A1c2f",  # Wallet 8
        "0x497506194d1Bc5D02597142D5A79D9198200118E",  # Wallet 9
    ],
    "GROUP_C": [
        "0x25dcd95A7a6D56eA4e781C7586306a4d9768227C",  # Wallet 10
        "0x51a35979C49354B2eD87F86eb1A679815753c331",  # Wallet 11
        "0xa9B5be1fc07E0538A5278beedB3A45bb3fbDC893",  # Wallet 12
        "0x5979857213bb73233aDBf029a7454DFb00A33539",  # Wallet 13
    ],
    "GROUP_D": [
        "0x9d1cA39386cb3D35c66674aA0Ce41e3403731241",  # Wallet 14
        "0xFD930dB05F90885DEd7Db693057E5B899b528b2b",  # Wallet 15
        "0x06d9681C02E2b5182C3489477f4b09D38f3959B2",  # Wallet 16
        "0x4007Fb7b726111153C07db0B3f1f561F8bad9853",  # Wallet 17
    ]
}

# 새로운 페어 목록
NEW_PAIRS = ["APEX", "STBL", "ZEC", "FF", "0G", "2Z", "EDEN"]

async def fetch_wallet_data(addresses: List[str]) -> Dict:
    """지갑 데이터 조회"""
    async with aiohttp.ClientSession() as session:
        data = {"addresses": addresses}
        async with session.post("http://localhost:8000/api/fetch_accounts", json=data) as response:
            return await response.json()

async def fetch_market_prices() -> Dict:
    """시장 가격 조회"""
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:8000/api/market_prices") as response:
            return await response.json()

def calculate_wallet_capacity(account_data: Dict) -> Dict:
    """지갑별 사용 가능 용량 계산"""
    wallet_capacity = {}

    for account in account_data.get("accounts", []):
        address = account["l1_address"]
        collateral = float(account.get("collateral", 0))

        # 현재 사용 중인 마진 계산
        used_margin = 0
        for pos in account.get("positions", []):
            position_value = float(pos.get("position_value", 0))
            leverage_str = pos.get("leverage", "3.0x")
            leverage = float(leverage_str.replace("x", ""))
            margin = position_value / leverage if leverage > 0 else 0
            used_margin += margin

        # 90% 담보 활용률
        max_margin = collateral * 0.9
        available_margin = max(0, max_margin - used_margin)

        wallet_capacity[address] = {
            "collateral": collateral,
            "used_margin": used_margin,
            "available_margin": available_margin,
            "utilization_rate": (used_margin / max_margin * 100) if max_margin > 0 else 0
        }

    return wallet_capacity

def generate_intra_group_hedge(group_name: str, wallet_capacities: Dict, market_prices: Dict) -> List[Dict]:
    """그룹 내 헷징 포지션 생성"""

    group_wallets = WALLET_GROUPS[group_name]
    positions = []

    # 그룹 내에서 사용 가능한 지갑만 필터링
    available_wallets = [
        addr for addr in group_wallets
        if addr in wallet_capacities and wallet_capacities[addr]["available_margin"] > 10
    ]

    if len(available_wallets) < 2:
        return []

    # 토큰별 롱/숏 페어 생성
    used_tokens = set()

    for token in NEW_PAIRS:
        if len(available_wallets) < 2:
            break

        # 토큰 중복 사용 방지
        if token in used_tokens:
            continue

        # 2개 지갑 선택 (가용 마진이 많은 순)
        sorted_wallets = sorted(
            available_wallets,
            key=lambda x: wallet_capacities[x]["available_margin"],
            reverse=True
        )

        wallet_long = sorted_wallets[0]
        wallet_short = sorted_wallets[1]

        # 포지션 크기 결정 (작은 쪽 지갑 기준)
        min_margin = min(
            wallet_capacities[wallet_long]["available_margin"],
            wallet_capacities[wallet_short]["available_margin"]
        )

        # 3x 레버리지로 최대 마진의 80% 사용
        position_margin = min(min_margin * 0.8, 50)  # 최대 50달러

        if position_margin >= 10:  # 최소 10달러
            # 롱 포지션
            positions.append({
                "wallet_address": wallet_long,
                "wallet_num": group_wallets.index(wallet_long) + 1,
                "token": token,
                "side": "LONG",
                "margin": round(position_margin, 2),
                "leverage": 3,
                "notional": round(position_margin * 3, 2),
                "pair_id": f"{token}_HEDGE",
                "hedge_partner": wallet_short
            })

            # 숏 포지션 (헷지)
            positions.append({
                "wallet_address": wallet_short,
                "wallet_num": group_wallets.index(wallet_short) + 1,
                "token": token,
                "side": "SHORT",
                "margin": round(position_margin, 2),
                "leverage": 3,
                "notional": round(position_margin * 3, 2),
                "pair_id": f"{token}_HEDGE",
                "hedge_partner": wallet_long
            })

            # 사용한 마진 업데이트
            wallet_capacities[wallet_long]["available_margin"] -= position_margin
            wallet_capacities[wallet_short]["available_margin"] -= position_margin

            # 사용된 토큰 표시
            used_tokens.add(token)

            # 사용된 지갑을 임시로 제거
            if wallet_capacities[wallet_long]["available_margin"] < 10:
                available_wallets.remove(wallet_long)
            if wallet_capacities[wallet_short]["available_margin"] < 10:
                available_wallets.remove(wallet_short)

    return positions

def calculate_group_delta(positions: List[Dict]) -> Dict:
    """그룹 내 델타 중립성 계산"""

    long_exposure = defaultdict(float)
    short_exposure = defaultdict(float)

    for pos in positions:
        token = pos["token"]
        notional = pos["notional"]

        if pos["side"] == "LONG":
            long_exposure[token] += notional
        else:
            short_exposure[token] += notional

    # 넷 익스포저 계산
    net_exposure = {}
    total_imbalance = 0

    all_tokens = set(list(long_exposure.keys()) + list(short_exposure.keys()))
    for token in all_tokens:
        long = long_exposure.get(token, 0)
        short = short_exposure.get(token, 0)
        net = long - short
        net_exposure[token] = net
        total_imbalance += abs(net)

    delta_score = max(0, 100 - (total_imbalance / 10))

    return {
        "long_exposure": dict(long_exposure),
        "short_exposure": dict(short_exposure),
        "net_exposure": net_exposure,
        "total_imbalance": total_imbalance,
        "delta_score": delta_score
    }

def print_group_report(group_name: str, positions: List[Dict], delta_analysis: Dict, wallet_capacities: Dict):
    """그룹 리포트 출력"""

    print(f"\n{'='*80}")
    print(f"🎯 {group_name} INTRA-GROUP HEDGING STRATEGY")
    print(f"{'='*80}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 그룹 개요
    group_wallets = WALLET_GROUPS[group_name]
    total_collateral = sum(wallet_capacities.get(addr, {}).get("collateral", 0) for addr in group_wallets)
    total_margin_used = sum(pos["margin"] for pos in positions)
    total_notional = sum(pos["notional"] for pos in positions)

    print(f"\n📊 GROUP OVERVIEW:")
    print(f"    Wallets: {len(group_wallets)}")
    print(f"    Total Collateral: ${total_collateral:.2f}")
    print(f"    Positions Created: {len(positions)}")
    print(f"    Total Margin Used: ${total_margin_used:.2f}")
    print(f"    Total Notional Volume: ${total_notional:.2f}")

    # 델타 중립성
    print(f"\n⚖️ DELTA NEUTRALITY:")
    print(f"    Delta Score: {delta_analysis['delta_score']:.1f}/100")
    print(f"    Total Imbalance: ${delta_analysis['total_imbalance']:.2f}")

    # 헷징 페어
    print(f"\n🔗 HEDGING PAIRS:")
    hedge_pairs = {}
    for pos in positions:
        pair_id = pos["pair_id"]
        if pair_id not in hedge_pairs:
            hedge_pairs[pair_id] = []
        hedge_pairs[pair_id].append(pos)

    for pair_id, pair_positions in hedge_pairs.items():
        if len(pair_positions) == 2:
            long_pos = next(p for p in pair_positions if p["side"] == "LONG")
            short_pos = next(p for p in pair_positions if p["side"] == "SHORT")

            print(f"\n    {long_pos['token']} Hedge Pair:")
            print(f"      🟢 LONG  | Wallet {long_pos['wallet_num']:2} | ${long_pos['notional']:7.2f}")
            print(f"      🔴 SHORT | Wallet {short_pos['wallet_num']:2} | ${short_pos['notional']:7.2f}")

    # 지갑별 상세
    print(f"\n💰 WALLET DETAILS:")
    for addr in group_wallets:
        wallet_num = group_wallets.index(addr) + 1
        capacity = wallet_capacities.get(addr, {})

        wallet_positions = [p for p in positions if p["wallet_address"] == addr]
        position_count = len(wallet_positions)
        margin_used = sum(p["margin"] for p in wallet_positions)

        print(f"\n    Wallet {wallet_num:2} (...{addr[-6:]}):")
        print(f"      Collateral: ${capacity.get('collateral', 0):8.2f}")
        print(f"      Margin Used: ${margin_used:7.2f}")
        print(f"      Available: ${capacity.get('available_margin', 0):9.2f}")
        print(f"      Positions: {position_count}")

        for pos in wallet_positions:
            symbol = "🟢" if pos["side"] == "LONG" else "🔴"
            print(f"        {symbol} {pos['side']} {pos['token']} | ${pos['notional']:.2f}")

async def main():
    """메인 실행 - GROUP_A만 실행"""

    print("🚀 Starting Group A Intra-Hedging Strategy...")

    # GROUP_A 지갑 데이터 조회
    group_a_wallets = WALLET_GROUPS["GROUP_A"]

    print(f"📡 Fetching data for {len(group_a_wallets)} wallets in GROUP_A...")
    wallet_data = await fetch_wallet_data(group_a_wallets)
    market_prices = await fetch_market_prices()

    # 지갑 용량 계산
    wallet_capacities = calculate_wallet_capacity(wallet_data)

    # GROUP_A 헷징 포지션 생성
    positions = generate_intra_group_hedge("GROUP_A", wallet_capacities, market_prices)

    # 델타 분석
    delta_analysis = calculate_group_delta(positions)

    # 리포트 출력
    print_group_report("GROUP_A", positions, delta_analysis, wallet_capacities)

    # JSON 저장
    save_data = {
        "timestamp": datetime.now().isoformat(),
        "group": "GROUP_A",
        "positions": positions,
        "delta_analysis": delta_analysis,
        "summary": {
            "total_positions": len(positions),
            "total_margin": sum(p["margin"] for p in positions),
            "total_notional": sum(p["notional"] for p in positions),
            "delta_score": delta_analysis["delta_score"]
        }
    }

    with open("group_a_hedging.json", "w") as f:
        json.dump(save_data, f, indent=2)

    print(f"\n📁 Strategy saved to: group_a_hedging.json")
    print(f"\n{'='*80}")

if __name__ == "__main__":
    asyncio.run(main())