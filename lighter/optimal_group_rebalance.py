#!/usr/bin/env python3
import asyncio
import aiohttp
import json
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict

# 17개 모든 지갑 주소
ALL_WALLETS = [
    {"num": 1, "addr": "0xC74Ef16B20c50B7337585a0a8e1eed3EDd50CF43"},
    {"num": 2, "addr": "0xe67b28750153E7D95Ff001b2557EbA6C5F56092c"},
    {"num": 3, "addr": "0x7878AE8C54227440293a0BB83b63F39DC24A0899"},
    {"num": 4, "addr": "0xe5909A5817325797f8Ed2C4c079f6c78B5E9bfa2"},
    {"num": 5, "addr": "0x29855eB076f6d4a571890a75fe8944380ca6ccC6"},
    {"num": 6, "addr": "0x8b49af69dF8d44C735812D30A3A5c66BA6fc05Fc"},
    {"num": 7, "addr": "0xE81261c93c99b4DCE06068adC0C2a7fFE425732f"},
    {"num": 8, "addr": "0x349f3e1db87719CE7c1013AE7b7Feb70053A1c2f"},
    {"num": 9, "addr": "0x497506194d1Bc5D02597142D5A79D9198200118E"},
    {"num": 10, "addr": "0x25dcd95A7a6D56eA4e781C7586306a4d9768227C"},
    {"num": 11, "addr": "0x51a35979C49354B2eD87F86eb1A679815753c331"},
    {"num": 12, "addr": "0xa9B5be1fc07E0538A5278beedB3A45bb3fbDC893"},
    {"num": 13, "addr": "0x5979857213bb73233aDBf029a7454DFb00A33539"},
    {"num": 14, "addr": "0x9d1cA39386cb3D35c66674aA0Ce41e3403731241"},
    {"num": 15, "addr": "0xFD930dB05F90885DEd7Db693057E5B899b528b2b"},
    {"num": 16, "addr": "0x06d9681C02E2b5182C3489477f4b09D38f3959B2"},
    {"num": 17, "addr": "0x4007Fb7b726111153C07db0B3f1f561F8bad9853"},
]

NEW_PAIRS = ["APEX", "STBL", "ZEC", "FF", "0G", "2Z", "EDEN"]

async def fetch_all_data():
    """모든 지갑 데이터 조회"""
    addresses = [w["addr"] for w in ALL_WALLETS]

    async with aiohttp.ClientSession() as session:
        # 포지션 조회
        data = {"addresses": addresses}
        async with session.post("http://localhost:8000/api/fetch_accounts", json=data) as response:
            portfolio_data = await response.json()

        # 시장 가격 조회
        async with session.get("http://localhost:8000/api/market_prices") as response:
            market_prices = await response.json()

    return portfolio_data, market_prices

def analyze_wallet_profiles(portfolio_data):
    """각 지갑의 프로필 분석"""

    wallet_profiles = {}

    for account in portfolio_data.get("accounts", []):
        address = account["l1_address"]
        wallet_num = next((w["num"] for w in ALL_WALLETS if w["addr"] == address), 0)

        collateral = float(account.get("collateral", 0))
        positions = account.get("positions", [])

        # 현재 사용 중인 마진 계산
        used_margin = 0
        total_exposure = 0
        token_exposure = defaultdict(float)
        long_exposure = 0
        short_exposure = 0

        for pos in positions:
            token = pos.get("symbol", "Unknown")
            side = "LONG" if pos.get("sign", 1) == 1 else "SHORT"
            amount = float(pos.get("position", 0))
            current = float(pos.get("current_price", 0))
            exposure = abs(amount * current)

            # 마진 계산
            position_value = float(pos.get("position_value", 0))
            leverage_str = pos.get("leverage", "3.0x")
            leverage = float(leverage_str.replace("x", ""))
            margin = position_value / leverage if leverage > 0 else 0
            used_margin += margin

            total_exposure += exposure
            token_exposure[token] += exposure

            if side == "LONG":
                long_exposure += exposure
            else:
                short_exposure += exposure

        # 가용 마진 계산
        max_margin = collateral * 0.9
        available_margin = max(0, max_margin - used_margin)
        utilization_rate = (used_margin / max_margin * 100) if max_margin > 0 else 0

        # 델타 bias 계산
        delta_bias = (long_exposure - short_exposure) / total_exposure if total_exposure > 0 else 0

        wallet_profiles[wallet_num] = {
            "address": address,
            "collateral": collateral,
            "used_margin": used_margin,
            "available_margin": available_margin,
            "utilization_rate": utilization_rate,
            "total_exposure": total_exposure,
            "long_exposure": long_exposure,
            "short_exposure": short_exposure,
            "delta_bias": delta_bias,
            "position_count": len(positions),
            "token_exposure": dict(token_exposure),
            "complexity_score": len(token_exposure) * (1 + abs(delta_bias))
        }

    return wallet_profiles

def create_balanced_groups(wallet_profiles):
    """균형 잡힌 4개 그룹 생성"""

    # 지갑들을 다양한 기준으로 정렬
    wallets = list(wallet_profiles.items())

    # 담보 기준 정렬
    by_collateral = sorted(wallets, key=lambda x: x[1]["collateral"], reverse=True)

    # 가용 마진 기준 정렬
    by_available = sorted(wallets, key=lambda x: x[1]["available_margin"], reverse=True)

    # 델타 bias 기준 정렬
    by_delta = sorted(wallets, key=lambda x: x[1]["delta_bias"])

    # 복잡성 점수 기준 정렬
    by_complexity = sorted(wallets, key=lambda x: x[1]["complexity_score"])

    print("\n" + "="*80)
    print("📊 WALLET ANALYSIS FOR OPTIMAL GROUPING")
    print("="*80)

    print("\n💰 TOP WALLETS BY COLLATERAL:")
    for i, (num, profile) in enumerate(by_collateral[:8]):
        print(f"  {i+1:2}. Wallet {num:2} | Collateral: ${profile['collateral']:8.2f} | Available: ${profile['available_margin']:7.2f}")

    print("\n🔄 WALLETS BY DELTA BIAS:")
    for i, (num, profile) in enumerate(by_delta):
        bias_symbol = "🟢" if profile['delta_bias'] > 0.1 else "🔴" if profile['delta_bias'] < -0.1 else "⚖️"
        print(f"  {bias_symbol} Wallet {num:2} | Delta Bias: {profile['delta_bias']:+6.2f} | Exposure: ${profile['total_exposure']:8.2f}")

    # 균형 잡힌 그룹 생성 알고리즘
    groups = {"GROUP_A": [], "GROUP_B": [], "GROUP_C": [], "GROUP_D": []}
    group_names = list(groups.keys())

    # 1단계: 담보가 큰 지갑들을 각 그룹에 하나씩 배분
    for i, (num, profile) in enumerate(by_collateral[:4]):
        groups[group_names[i]].append(num)

    # 2단계: 가용 마진이 많은 지갑들을 균등 배분
    available_wallets = [num for num, profile in by_available[4:] if profile["available_margin"] > 5]
    for i, num in enumerate(available_wallets[:8]):
        group_idx = i % 4
        groups[group_names[group_idx]].append(num)

    # 3단계: 나머지 지갑들을 델타 bias를 고려하여 배분
    remaining_wallets = []
    for num, profile in wallets:
        if not any(num in group for group in groups.values()):
            remaining_wallets.append((num, profile))

    # 델타 bias 균형을 위해 배분
    for num, profile in remaining_wallets:
        # 각 그룹의 현재 델타 bias 계산
        group_deltas = {}
        for group_name, group_wallets in groups.items():
            total_long = sum(wallet_profiles[w]["long_exposure"] for w in group_wallets)
            total_short = sum(wallet_profiles[w]["short_exposure"] for w in group_wallets)
            total_exp = total_long + total_short
            group_deltas[group_name] = (total_long - total_short) / total_exp if total_exp > 0 else 0

        # 현재 지갑의 bias와 반대되는 그룹 찾기
        wallet_bias = profile["delta_bias"]
        best_group = None
        best_balance = float('inf')

        for group_name in group_names:
            if len(groups[group_name]) < 5:  # 그룹당 최대 5개
                group_bias = group_deltas[group_name]
                # 지갑을 추가했을 때의 balance 계산
                new_balance = abs(group_bias + wallet_bias)
                if new_balance < best_balance:
                    best_balance = new_balance
                    best_group = group_name

        if best_group:
            groups[best_group].append(num)

    return groups

def calculate_group_stats(groups, wallet_profiles):
    """그룹별 통계 계산"""

    group_stats = {}

    for group_name, wallet_nums in groups.items():
        total_collateral = sum(wallet_profiles[num]["collateral"] for num in wallet_nums)
        total_available = sum(wallet_profiles[num]["available_margin"] for num in wallet_nums)
        total_exposure = sum(wallet_profiles[num]["total_exposure"] for num in wallet_nums)
        total_long = sum(wallet_profiles[num]["long_exposure"] for num in wallet_nums)
        total_short = sum(wallet_profiles[num]["short_exposure"] for num in wallet_nums)

        group_delta = (total_long - total_short) / total_exposure if total_exposure > 0 else 0

        group_stats[group_name] = {
            "wallet_count": len(wallet_nums),
            "total_collateral": total_collateral,
            "total_available": total_available,
            "total_exposure": total_exposure,
            "group_delta": group_delta,
            "wallets": wallet_nums
        }

    return group_stats

def print_grouping_report(groups, wallet_profiles, group_stats):
    """그룹핑 리포트 출력"""

    print("\n" + "="*80)
    print("🎯 OPTIMIZED 4-GROUP DIVISION")
    print("="*80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 전체 요약
    total_collateral = sum(stats["total_collateral"] for stats in group_stats.values())
    total_available = sum(stats["total_available"] for stats in group_stats.values())

    print(f"\n📊 OVERALL SUMMARY:")
    print(f"    Total Wallets: 17")
    print(f"    Total Collateral: ${total_collateral:.2f}")
    print(f"    Total Available Margin: ${total_available:.2f}")

    # 그룹별 상세
    for group_name in ["GROUP_A", "GROUP_B", "GROUP_C", "GROUP_D"]:
        if group_name not in group_stats:
            continue

        stats = group_stats[group_name]
        wallets = groups[group_name]

        print(f"\n{'='*40}")
        print(f"📋 {group_name}")
        print(f"{'='*40}")
        print(f"  Wallets: {stats['wallet_count']}")
        print(f"  Total Collateral: ${stats['total_collateral']:10.2f}")
        print(f"  Available Margin: ${stats['total_available']:10.2f}")
        print(f"  Total Exposure: ${stats['total_exposure']:12.2f}")
        print(f"  Group Delta Bias: {stats['group_delta']:+8.2f}")

        print(f"\n  Wallet Details:")
        for wallet_num in sorted(wallets):
            profile = wallet_profiles[wallet_num]
            bias_symbol = "🟢" if profile['delta_bias'] > 0.1 else "🔴" if profile['delta_bias'] < -0.1 else "⚖️"
            print(f"    {bias_symbol} Wallet {wallet_num:2} | Collateral: ${profile['collateral']:8.2f} | "
                  f"Available: ${profile['available_margin']:7.2f} | Delta: {profile['delta_bias']:+6.2f}")

    # 균형성 분석
    print(f"\n{'='*80}")
    print("⚖️ GROUP BALANCE ANALYSIS")
    print(f"{'='*80}")

    collateral_std = calculate_std([stats["total_collateral"] for stats in group_stats.values()])
    available_std = calculate_std([stats["total_available"] for stats in group_stats.values()])
    delta_std = calculate_std([abs(stats["group_delta"]) for stats in group_stats.values()])

    print(f"  Collateral Balance Score: {max(0, 100 - collateral_std):.1f}/100")
    print(f"  Available Margin Balance: {max(0, 100 - available_std):.1f}/100")
    print(f"  Delta Neutrality Balance: {max(0, 100 - delta_std*100):.1f}/100")

    return groups

def calculate_std(values):
    """표준편차 계산"""
    if not values:
        return 0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance ** 0.5

async def main():
    """메인 실행"""

    print("🔄 Fetching all wallet data...")
    portfolio_data, market_prices = await fetch_all_data()

    print("📊 Analyzing wallet profiles...")
    wallet_profiles = analyze_wallet_profiles(portfolio_data)

    print("🎯 Creating balanced groups...")
    groups = create_balanced_groups(wallet_profiles)

    print("📈 Calculating group statistics...")
    group_stats = calculate_group_stats(groups, wallet_profiles)

    # 리포트 출력
    optimized_groups = print_grouping_report(groups, wallet_profiles, group_stats)

    # JSON 저장
    save_data = {
        "timestamp": datetime.now().isoformat(),
        "groups": {
            group_name: {
                "wallets": [{"num": num, "addr": next(w["addr"] for w in ALL_WALLETS if w["num"] == num)}
                          for num in wallet_nums],
                "stats": group_stats[group_name]
            }
            for group_name, wallet_nums in optimized_groups.items()
        },
        "balance_scores": {
            "collateral_balance": max(0, 100 - calculate_std([group_stats[g]["total_collateral"] for g in group_stats])),
            "available_balance": max(0, 100 - calculate_std([group_stats[g]["total_available"] for g in group_stats])),
            "delta_balance": max(0, 100 - calculate_std([abs(group_stats[g]["group_delta"]) for g in group_stats])*100)
        }
    }

    with open("optimized_groups.json", "w") as f:
        json.dump(save_data, f, indent=2)

    print(f"\n📁 Optimized groups saved to: optimized_groups.json")
    print(f"\n{'='*80}")

if __name__ == "__main__":
    asyncio.run(main())