#!/usr/bin/env python3
import asyncio
import aiohttp
import json
import random
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

# 새로운 페어 목록
NEW_PAIRS = ["APEX", "STBL", "ZEC", "FF", "0G", "2Z", "EDEN"]

# 지갑 정보 (실제 담보 기준)
WALLET_INFO = [
    {"address": "0xC74Ef16B20c50B7337585a0a8e1eed3EDd50CF43", "collateral": 23.93, "index": 1},
    {"address": "0xe67b28750153E7D95Ff001b2557EbA6C5F56092c", "collateral": 24.17, "index": 2},
    {"address": "0x7878AE8C54227440293a0BB83b63F39DC24A0899", "collateral": 120.58, "index": 3},
    {"address": "0xe5909A5817325797f8Ed2C4c079f6c78B5E9bfa2", "collateral": 8.77, "index": 4},
    {"address": "0x29855eB076f6d4a571890a75fe8944380ca6ccC6", "collateral": 106.28, "index": 5},
    {"address": "0x8b49af69dF8d44C735812D30A3A5c66BA6fc05Fc", "collateral": 186.61, "index": 6},
    {"address": "0xE81261c93c99b4DCE06068adC0C2a7fFE425732f", "collateral": 76.98, "index": 7},
    {"address": "0x349f3e1db87719CE7c1013AE7b7Feb70053A1c2f", "collateral": 3.83, "index": 8},
    {"address": "0x497506194d1Bc5D02597142D5A79D9198200118E", "collateral": 152.03, "index": 9},
    {"address": "0x25dcd95A7a6D56eA4e781C7586306a4d9768227C", "collateral": 58.50, "index": 10},
    {"address": "0x51a35979C49354B2eD87F86eb1A679815753c331", "collateral": 34.46, "index": 11},
    {"address": "0xa9B5be1fc07E0538A5278beedB3A45bb3fbDC893", "collateral": 103.36, "index": 12},
    {"address": "0x5979857213bb73233aDBf029a7454DFb00A33539", "collateral": 57.04, "index": 13},
    {"address": "0x9d1cA39386cb3D35c66674aA0Ce41e3403731241", "collateral": 100.72, "index": 14},
    {"address": "0xFD930dB05F90885DEd7Db693057E5B899b528b2b", "collateral": 100.71, "index": 15},
    {"address": "0x06d9681C02E2b5182C3489477f4b09D38f3959B2", "collateral": 76.54, "index": 16},
]

def divide_into_groups(wallets: List[Dict]) -> Dict[str, List[Dict]]:
    """지갑을 4개 그룹으로 분배

    전략: 각 그룹이 균형잡힌 담보를 갖도록 대/중/소 지갑 혼합
    """

    # 담보 크기별로 정렬
    sorted_wallets = sorted(wallets, key=lambda x: x["collateral"], reverse=True)

    # 4개 그룹 초기화
    groups = {
        "GROUP_A": [],  # APEX/STBL 중심
        "GROUP_B": [],  # ZEC/FF 중심
        "GROUP_C": [],  # 0G/2Z 중심
        "GROUP_D": [],  # EDEN/Mixed 중심
    }

    # 그룹별 총 담보 추적
    group_collaterals = {"GROUP_A": 0, "GROUP_B": 0, "GROUP_C": 0, "GROUP_D": 0}

    # 지갑을 그룹에 균등 분배 (대액 먼저)
    group_names = list(groups.keys())

    for i, wallet in enumerate(sorted_wallets):
        # 가장 적은 담보를 가진 그룹에 추가
        min_group = min(group_collaterals.items(), key=lambda x: x[1])[0]
        groups[min_group].append(wallet)
        group_collaterals[min_group] += wallet["collateral"]

    return groups

def generate_group_positions(group_name: str, wallets: List[Dict], group_start_hour: int) -> List[Dict]:
    """그룹별 포지션 생성 (그룹 내 헷징)

    각 그룹은 특정 토큰 페어에 집중하여 그룹 내에서 델타 중립 달성
    """

    # 그룹별 주력 토큰 설정
    group_tokens = {
        "GROUP_A": ["APEX", "STBL", "ZEC"],    # 안정적 토큰
        "GROUP_B": ["ZEC", "FF", "EDEN"],       # 중간 변동성
        "GROUP_C": ["0G", "2Z", "FF"],          # 고변동성
        "GROUP_D": ["EDEN", "STBL", "APEX"],    # 혼합 전략
    }

    primary_tokens = group_tokens[group_name]
    all_positions = []

    # 그룹 내 포지션 밸런싱을 위한 추적
    group_long_exposure = defaultdict(float)
    group_short_exposure = defaultdict(float)

    for wallet_idx, wallet in enumerate(wallets):
        wallet_positions = []
        collateral = wallet["collateral"]

        # 사용 가능한 마진 (85%)
        available_margin = collateral * 0.85

        # 포지션 개수 결정
        if collateral < 20:
            num_positions = 1
        elif collateral < 50:
            num_positions = 2
        elif collateral < 100:
            num_positions = 3
        else:
            num_positions = 4

        margin_per_position = available_margin / num_positions

        # 사용된 토큰 추적 (지갑별)
        used_tokens = set()

        for pos_idx in range(num_positions):
            # 토큰 선택 (주력 토큰 우선, 이미 사용한 토큰 제외)
            available_tokens = [t for t in primary_tokens if t not in used_tokens]
            if not available_tokens:
                available_tokens = [t for t in NEW_PAIRS if t not in used_tokens]
            if not available_tokens:
                break

            token = random.choice(available_tokens)
            used_tokens.add(token)

            # 그룹 내 델타 밸런싱을 위한 방향 결정
            token_net_exposure = group_long_exposure[token] - group_short_exposure[token]

            # 델타가 치우친 경우 반대 방향 선호
            if abs(token_net_exposure) > 100:
                side = "SHORT" if token_net_exposure > 0 else "LONG"
            else:
                # 균형잡힌 경우 교대로
                side = "LONG" if (wallet_idx + pos_idx) % 2 == 0 else "SHORT"

            # 마진 계산 (약간의 변동성)
            actual_margin = margin_per_position * random.uniform(0.9, 1.1)
            actual_margin = round(actual_margin, 2)

            # 익스포저 업데이트
            exposure = actual_margin * 3  # 3x 레버리지
            if side == "LONG":
                group_long_exposure[token] += exposure
            else:
                group_short_exposure[token] += exposure

            # 진입 시간 (그룹별로 다른 시간대)
            entry_time = datetime.now() + timedelta(
                hours=group_start_hour + pos_idx * 2 + random.uniform(0, 1),
                minutes=random.randint(0, 59)
            )

            wallet_positions.append({
                "token": token,
                "side": side,
                "margin": actual_margin,
                "leverage": 3,
                "notional_value": exposure,
                "entry_time": entry_time
            })

        all_positions.append({
            "wallet": wallet["address"],
            "wallet_index": wallet["index"],
            "collateral": wallet["collateral"],
            "group": group_name,
            "positions": wallet_positions,
            "total_margin_used": sum(p["margin"] for p in wallet_positions)
        })

    return all_positions, {
        "long_exposure": dict(group_long_exposure),
        "short_exposure": dict(group_short_exposure),
        "net_exposure": {
            token: group_long_exposure[token] - group_short_exposure[token]
            for token in set(list(group_long_exposure.keys()) + list(group_short_exposure.keys()))
        }
    }

def generate_execution_schedule(groups: Dict[str, List[Dict]]) -> Dict[str, Dict]:
    """그룹별 실행 일정 생성

    각 그룹은 다른 시간대에 진입하여 가격 영향 최소화
    """

    schedule = {}

    # 그룹별 시작 시간 (6시간 간격)
    group_start_times = {
        "GROUP_A": 0,    # 즉시 시작
        "GROUP_B": 6,    # 6시간 후
        "GROUP_C": 12,   # 12시간 후
        "GROUP_D": 18,   # 18시간 후
    }

    for group_name, start_hour in group_start_times.items():
        schedule[group_name] = {
            "start_time": datetime.now() + timedelta(hours=start_hour),
            "execution_window": "3 hours",  # 3시간 내 모든 포지션 진입
            "rebalance_schedule": [
                datetime.now() + timedelta(hours=start_hour + 24),  # Day 2
                datetime.now() + timedelta(hours=start_hour + 48),  # Day 3
                datetime.now() + timedelta(hours=start_hour + 96),  # Day 5
            ]
        }

    return schedule

def calculate_group_metrics(group_positions: List[Dict], group_stats: Dict) -> Dict:
    """그룹별 메트릭 계산"""

    total_margin = sum(p["total_margin_used"] for p in group_positions)
    total_collateral = sum(p["collateral"] for p in group_positions)
    total_positions = sum(len(p["positions"]) for p in group_positions)

    # 델타 중립성 점수 계산
    total_net = sum(abs(v) for v in group_stats["net_exposure"].values())
    neutrality_score = max(0, 100 - (total_net / 10))

    return {
        "total_collateral": total_collateral,
        "total_margin_used": total_margin,
        "margin_utilization": (total_margin / total_collateral * 100) if total_collateral > 0 else 0,
        "total_positions": total_positions,
        "neutrality_score": neutrality_score,
        "long_exposure": group_stats["long_exposure"],
        "short_exposure": group_stats["short_exposure"],
        "net_exposure": group_stats["net_exposure"]
    }

def generate_report(all_groups_data: Dict) -> str:
    """그룹 헷징 전략 리포트 생성"""

    report = []
    report.append("\n" + "="*80)
    report.append("GROUP-BASED HEDGING STRATEGY")
    report.append("="*80)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Strategy: 4 Independent Groups with Intra-Group Hedging")
    report.append(f"Target Pairs: {', '.join(NEW_PAIRS)}")

    # 전체 요약
    total_collateral = sum(g["metrics"]["total_collateral"] for g in all_groups_data.values())
    total_margin = sum(g["metrics"]["total_margin_used"] for g in all_groups_data.values())
    total_positions = sum(g["metrics"]["total_positions"] for g in all_groups_data.values())

    report.append(f"\n📊 OVERALL SUMMARY")
    report.append(f"  Total Collateral: ${total_collateral:,.2f}")
    report.append(f"  Total Margin Used: ${total_margin:,.2f}")
    report.append(f"  Overall Utilization: {(total_margin/total_collateral*100):.1f}%")
    report.append(f"  Total Positions: {total_positions}")

    # 그룹별 상세 정보
    for group_name in ["GROUP_A", "GROUP_B", "GROUP_C", "GROUP_D"]:
        group_data = all_groups_data[group_name]
        metrics = group_data["metrics"]
        schedule = group_data["schedule"]
        positions = group_data["positions"]

        report.append(f"\n{'='*40}")
        report.append(f"📁 {group_name}")
        report.append(f"{'='*40}")

        # 그룹 메트릭
        report.append(f"\n  Group Metrics:")
        report.append(f"    Wallets: {len(positions)}")
        report.append(f"    Collateral: ${metrics['total_collateral']:,.2f}")
        report.append(f"    Margin Used: ${metrics['total_margin_used']:,.2f} ({metrics['margin_utilization']:.1f}%)")
        report.append(f"    Positions: {metrics['total_positions']}")
        report.append(f"    Delta Neutrality: {metrics['neutrality_score']:.1f}/100")

        # 익스포저
        report.append(f"\n  Net Exposure:")
        for token, net in sorted(metrics['net_exposure'].items(), key=lambda x: abs(x[1]), reverse=True):
            if abs(net) > 0.01:
                symbol = "🟢" if net > 0 else "🔴"
                long = metrics['long_exposure'].get(token, 0)
                short = metrics['short_exposure'].get(token, 0)
                report.append(f"    {symbol} {token}: ${net:+.2f} (L:${long:.0f}/S:${short:.0f})")

        # 실행 일정
        report.append(f"\n  Execution Schedule:")
        report.append(f"    Start: {schedule['start_time'].strftime('%m/%d %H:%M')}")
        report.append(f"    Window: {schedule['execution_window']}")
        report.append(f"    Rebalancing: {', '.join(t.strftime('%m/%d') for t in schedule['rebalance_schedule'])}")

        # 지갑별 포지션 (요약)
        report.append(f"\n  Wallet Positions:")
        for pos_data in positions[:3]:  # 상위 3개만 표시
            report.append(f"    Wallet {pos_data['wallet_index']} (${pos_data['collateral']:.2f}):")
            for pos in pos_data['positions']:
                report.append(f"      • {pos['side']} {pos['token']}: ${pos['margin']:.2f} @ 3x")
        if len(positions) > 3:
            report.append(f"    ... and {len(positions)-3} more wallets")

    # 실행 가이드
    report.append(f"\n{'='*80}")
    report.append(f"🎯 EXECUTION STRATEGY")
    report.append(f"{'='*80}")

    report.append("\n  Phase 1: Group Sequential Entry")
    report.append("    • GROUP_A: Immediate (0-3 hours)")
    report.append("    • GROUP_B: +6 hours (6-9 hours)")
    report.append("    • GROUP_C: +12 hours (12-15 hours)")
    report.append("    • GROUP_D: +18 hours (18-21 hours)")

    report.append("\n  Phase 2: Intra-Group Hedging")
    report.append("    • Each group maintains internal delta neutrality")
    report.append("    • Automatic rebalancing within groups")
    report.append("    • No cross-group coordination needed")

    report.append("\n  Phase 3: Volume Generation")
    report.append("    • 3-5 rebalances per position over 7 days")
    report.append("    • Partial close at +10%")
    report.append("    • Add position at -5%")
    report.append("    • Flip sides at key levels")

    # 리스크 관리
    report.append(f"\n⚠️ RISK MANAGEMENT")
    report.append("  • Group Independence: Each group operates independently")
    report.append("  • Price Impact: 6-hour gaps minimize market impact")
    report.append("  • Emergency Exit: -25% stop loss per position")
    report.append("  • Group Rebalancing: When group delta > $500")

    # 장점
    report.append(f"\n✅ ADVANTAGES")
    report.append("  • Faster Execution: ~15 minutes per group vs 1 hour for all")
    report.append("  • Price Stability: Groups enter at different price levels")
    report.append("  • Risk Isolation: Group failure doesn't affect others")
    report.append("  • Easier Management: 4 wallets at a time")

    report.append("\n" + "="*80)

    return "\n".join(report)

async def main():
    """메인 실행 함수"""

    print("Dividing wallets into 4 groups...")
    groups = divide_into_groups(WALLET_INFO)

    print("\nGroup Distribution:")
    for group_name, wallets in groups.items():
        total_collateral = sum(w["collateral"] for w in wallets)
        print(f"  {group_name}: {len(wallets)} wallets, ${total_collateral:.2f} collateral")

    print("\nGenerating positions for each group...")

    # 실행 일정 생성
    execution_schedule = generate_execution_schedule(groups)

    # 그룹별 포지션 생성
    all_groups_data = {}

    group_start_hours = {"GROUP_A": 0, "GROUP_B": 6, "GROUP_C": 12, "GROUP_D": 18}

    for group_name, wallets in groups.items():
        positions, group_stats = generate_group_positions(
            group_name,
            wallets,
            group_start_hours[group_name]
        )

        metrics = calculate_group_metrics(positions, group_stats)

        all_groups_data[group_name] = {
            "wallets": wallets,
            "positions": positions,
            "metrics": metrics,
            "schedule": execution_schedule[group_name]
        }

    # 리포트 생성
    report = generate_report(all_groups_data)
    print(report)

    # JSON 저장 (날짜 직렬화)
    save_data = {
        "timestamp": datetime.now().isoformat(),
        "groups": {}
    }

    for group_name, data in all_groups_data.items():
        save_data["groups"][group_name] = {
            "wallets": data["wallets"],
            "metrics": data["metrics"],
            "schedule": {
                "start_time": data["schedule"]["start_time"].isoformat(),
                "execution_window": data["schedule"]["execution_window"],
                "rebalance_schedule": [t.isoformat() for t in data["schedule"]["rebalance_schedule"]]
            },
            "positions": []
        }

        for pos_data in data["positions"]:
            save_positions = []
            for pos in pos_data["positions"]:
                save_positions.append({
                    **pos,
                    "entry_time": pos["entry_time"].isoformat()
                })

            save_data["groups"][group_name]["positions"].append({
                **pos_data,
                "positions": save_positions
            })

    with open("group_hedging_strategy.json", "w") as f:
        json.dump(save_data, f, indent=2)

    print(f"\n📁 Detailed strategy saved to: group_hedging_strategy.json")

if __name__ == "__main__":
    asyncio.run(main())