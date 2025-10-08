#!/usr/bin/env python3
import asyncio
import aiohttp
import json
import random
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta

# 새로운 페어 목록
NEW_PAIRS = ["APEX", "STBL", "ZEC", "FF", "0G", "2Z", "EDEN"]

# 지갑별 실제 담보 금액
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
    {"address": "0x4007Fb7b726111153C07db0B3f1f561F8bad9853", "collateral": 10.0, "index": 17}
]

async def fetch_market_data():
    """현재 시장 데이터 가져오기"""
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:8000/api/market_prices") as response:
            return await response.json()

def generate_volume_maximizing_positions(wallet_info: Dict, token_prices: Dict) -> List[Dict]:
    """거래량 최대화를 위한 포지션 생성

    전략:
    1. 담보의 90%까지 활용
    2. 레버리지 3배 고정
    3. 다중 포지션으로 분산
    4. 동일 토큰의 롱/숏 동시 보유 금지
    5. 빈번한 리밸런싱을 위한 구조
    """

    positions = []
    collateral = wallet_info["collateral"]

    # 사용 가능한 총 마진 (담보의 90%)
    available_margin = collateral * 0.9

    # 포지션 개수 결정 (담보 크기에 따라)
    if collateral < 10:
        num_positions = 1
    elif collateral < 30:
        num_positions = 2
    elif collateral < 100:
        num_positions = 3
    else:
        num_positions = 4

    # 각 포지션별 마진 할당
    margin_per_position = available_margin / num_positions

    # 사용된 토큰-사이드 조합 추적
    used_tokens = {}  # {token: side}
    available_tokens = NEW_PAIRS.copy()

    # 포지션 생성
    for i in range(num_positions):
        # 사용 가능한 토큰 선택
        if len(used_tokens) >= len(NEW_PAIRS):
            # 모든 토큰을 사용한 경우, 반대 방향으로만 가능
            token_choices = [t for t in NEW_PAIRS if t in used_tokens]
            if not token_choices:
                break  # 더 이상 포지션 불가
            token = random.choice(token_choices)
            # 기존과 반대 방향
            side = "SHORT" if used_tokens[token] == "LONG" else "LONG"
            # 이제 이 토큰은 더 이상 사용 불가
            del used_tokens[token]
        else:
            # 아직 사용하지 않은 토큰 선택
            unused_tokens = [t for t in NEW_PAIRS if t not in used_tokens]
            if not unused_tokens:
                break
            token = random.choice(unused_tokens)
            side = random.choice(["LONG", "SHORT"])
            used_tokens[token] = side

        # 마진에 약간의 변동성 추가 (리얼리즘)
        actual_margin = margin_per_position * random.uniform(0.95, 1.05)
        actual_margin = round(actual_margin, 2)

        positions.append({
            "token": token,
            "side": side,
            "margin": actual_margin,
            "leverage": 3,  # 고정 레버리지
            "notional_value": actual_margin * 3,  # 실제 거래량
            "entry_time": datetime.now() + timedelta(
                hours=i * 2 + random.randint(0, 1),
                minutes=random.randint(0, 59)
            )
        })

    return positions

def generate_rebalancing_schedule(positions: List[Dict]) -> List[Dict]:
    """리밸런싱 일정 생성 (거래량 증가 목적)

    각 포지션에 대해 주기적인 리밸런싱 일정 추가
    """
    rebalancing = []

    for pos in positions:
        # 각 포지션당 3-5회 리밸런싱
        num_rebalances = random.randint(3, 5)

        for i in range(num_rebalances):
            rebalance_time = pos["entry_time"] + timedelta(
                days=i + 1,
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )

            # 리밸런싱 타입
            rebalance_type = random.choice([
                "PARTIAL_CLOSE",  # 부분 청산 (50%)
                "ADD_POSITION",   # 포지션 추가
                "FLIP_SIDE",      # 방향 전환
                "ADJUST_SIZE"     # 크기 조정
            ])

            rebalancing.append({
                "token": pos["token"],
                "type": rebalance_type,
                "time": rebalance_time,
                "volume_impact": pos["notional_value"] * 0.5 if rebalance_type == "PARTIAL_CLOSE" else pos["notional_value"]
            })

    return rebalancing

def calculate_total_metrics(all_allocations: List[Dict]) -> Dict:
    """전체 메트릭 계산"""

    total_volume_24h = 0
    total_volume_7d = 0
    total_positions = 0
    total_margin_used = 0

    long_exposure = {}
    short_exposure = {}

    for allocation in all_allocations:
        for pos in allocation["positions"]:
            # 24시간 거래량 (초기 + 첫 리밸런싱)
            total_volume_24h += pos["notional_value"]

            # 7일 거래량 (모든 리밸런싱 포함)
            total_volume_7d += pos["notional_value"]

            # 리밸런싱 거래량 추가
            for rebal in allocation.get("rebalancing", []):
                if rebal["token"] == pos["token"]:
                    total_volume_7d += rebal["volume_impact"]
                    # 첫 24시간 내 리밸런싱
                    if (rebal["time"] - pos["entry_time"]).total_seconds() < 86400:
                        total_volume_24h += rebal["volume_impact"]

            total_positions += 1
            total_margin_used += pos["margin"]

            # 익스포저 계산
            token = pos["token"]
            exposure = pos["notional_value"]

            if pos["side"] == "LONG":
                long_exposure[token] = long_exposure.get(token, 0) + exposure
            else:
                short_exposure[token] = short_exposure.get(token, 0) + exposure

    # 델타 계산
    net_exposure = {}
    for token in set(list(long_exposure.keys()) + list(short_exposure.keys())):
        long = long_exposure.get(token, 0)
        short = short_exposure.get(token, 0)
        net_exposure[token] = long - short

    total_collateral = sum(w["collateral"] for w in WALLET_INFO)

    return {
        "total_volume_24h": total_volume_24h,
        "total_volume_7d": total_volume_7d,
        "total_positions": total_positions,
        "total_margin_used": total_margin_used,
        "total_collateral": total_collateral,
        "margin_utilization": (total_margin_used / total_collateral) * 100,
        "avg_position_size": total_margin_used / total_positions if total_positions > 0 else 0,
        "long_exposure": long_exposure,
        "short_exposure": short_exposure,
        "net_exposure": net_exposure,
        "total_net_delta": sum(net_exposure.values())
    }

def generate_report(allocations: List[Dict], metrics: Dict) -> str:
    """거래량 최대화 리포트 생성"""

    report = []
    report.append("\n" + "="*80)
    report.append("VOLUME MAXIMIZING PORTFOLIO STRATEGY")
    report.append("="*80)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Target Pairs: {', '.join(NEW_PAIRS)}")
    report.append(f"Fixed Leverage: 3x")

    # 거래량 메트릭
    report.append(f"\n📈 VOLUME METRICS")
    report.append(f"  Expected 24h Volume: ${metrics['total_volume_24h']:,.2f}")
    report.append(f"  Expected 7d Volume: ${metrics['total_volume_7d']:,.2f}")
    report.append(f"  Total Positions: {metrics['total_positions']}")
    report.append(f"  Average Position Size: ${metrics['avg_position_size']:.2f}")
    report.append(f"  Margin Utilization: {metrics['margin_utilization']:.1f}%")

    # 담보 활용도
    report.append(f"\n💰 COLLATERAL UTILIZATION")
    report.append(f"  Total Available: ${metrics['total_collateral']:,.2f}")
    report.append(f"  Total Used: ${metrics['total_margin_used']:,.2f}")
    report.append(f"  Utilization Rate: {metrics['margin_utilization']:.1f}%")

    # 토큰별 익스포저
    report.append(f"\n⚖️ TOKEN EXPOSURE (Notional)")
    for token in NEW_PAIRS:
        if token in metrics['net_exposure']:
            net = metrics['net_exposure'][token]
            long = metrics['long_exposure'].get(token, 0)
            short = metrics['short_exposure'].get(token, 0)
            total = long + short
            symbol = "🟢" if net > 0 else "🔴" if net < 0 else "⚪"
            report.append(f"  {symbol} {token}: Total ${total:,.2f} (L: ${long:.2f} / S: ${short:.2f})")

    # 지갑별 상세 할당
    report.append(f"\n📋 DETAILED WALLET ALLOCATIONS")

    # 거래량 기준 상위 10개 지갑만 상세 표시
    sorted_allocations = sorted(allocations,
                               key=lambda x: sum(p["notional_value"] for p in x["positions"]),
                               reverse=True)

    for i, allocation in enumerate(sorted_allocations[:10]):
        wallet_volume = sum(p["notional_value"] for p in allocation["positions"])
        report.append(f"\n  Wallet {allocation['wallet_index']} ({allocation['wallet'][:10]}...):")
        report.append(f"    Collateral: ${allocation['collateral']:.2f}")
        report.append(f"    Total Margin Used: ${allocation['total_margin_used']:.2f}")
        report.append(f"    Expected Volume: ${wallet_volume:.2f}")
        report.append(f"    Positions ({len(allocation['positions'])}):")

        for j, pos in enumerate(allocation["positions"], 1):
            report.append(f"      {j}. {pos['side']} {pos['token']}")
            report.append(f"         Margin: ${pos['margin']:.2f} @ {pos['leverage']}x")
            report.append(f"         Notional: ${pos['notional_value']:.2f}")
            report.append(f"         Entry: {pos['entry_time'].strftime('%m/%d %H:%M')}")

        # 리밸런싱 일정 요약
        rebal_count = len(allocation.get("rebalancing", []))
        if rebal_count > 0:
            report.append(f"    Scheduled Rebalances: {rebal_count}")

    # 나머지 지갑 요약
    if len(allocations) > 10:
        report.append(f"\n  ... and {len(allocations) - 10} more wallets")

    # 실행 전략
    report.append(f"\n🎯 VOLUME MAXIMIZATION STRATEGY")
    report.append("  1. AGGRESSIVE UTILIZATION: Use 90% of available collateral")
    report.append("  2. MULTIPLE POSITIONS: 1-4 positions per wallet based on size")
    report.append("  3. FREQUENT REBALANCING: 3-5 times per position over 7 days")
    report.append("  4. MIXED STRATEGIES: Long/Short on same tokens for volume")
    report.append("  5. STAGGERED ENTRIES: Spread over 48-72 hours")

    # 리밸런싱 전략
    report.append(f"\n🔄 REBALANCING TACTICS")
    report.append("  • PARTIAL CLOSE: Close 50% at +10% profit")
    report.append("  • ADD POSITION: Double down at -5% loss")
    report.append("  • FLIP SIDE: Switch direction at key levels")
    report.append("  • SIZE ADJUST: Increase/decrease by 30% based on momentum")

    # 리스크 관리
    report.append(f"\n⚠️ RISK PARAMETERS")
    report.append("  • Max Drawdown: 40% per position")
    report.append("  • Emergency Exit: -25% stop loss")
    report.append("  • Position Limit: Max 4 per wallet")
    report.append("  • Rebalance Trigger: ±10% PnL or 24 hours")

    # 예상 결과
    report.append(f"\n📊 EXPECTED OUTCOMES")
    report.append(f"  • 24h Volume: ${metrics['total_volume_24h']:,.2f}")
    report.append(f"  • 7d Volume: ${metrics['total_volume_7d']:,.2f}")
    report.append(f"  • Volume Multiplier: {(metrics['total_volume_7d'] / metrics['total_collateral']):.1f}x")
    report.append(f"  • Daily Avg Volume: ${metrics['total_volume_7d'] / 7:.2f}")

    report.append("\n" + "="*80)

    return "\n".join(report)

async def main():
    """메인 실행 함수"""

    print("Fetching market data...")
    market_data = await fetch_market_data()

    # 토큰 가격 추출
    token_prices = {}
    for token in NEW_PAIRS:
        if token in market_data:
            token_prices[token] = market_data[token].get("last_price", 1)

    print("Generating volume-maximizing positions...")

    all_allocations = []

    for wallet in WALLET_INFO:
        # 포지션 생성
        positions = generate_volume_maximizing_positions(wallet, token_prices)

        # 리밸런싱 일정 생성
        rebalancing = generate_rebalancing_schedule(positions)

        # 총 마진 계산
        total_margin = sum(p["margin"] for p in positions)

        allocation = {
            "wallet": wallet["address"],
            "wallet_index": wallet["index"],
            "collateral": wallet["collateral"],
            "total_margin_used": total_margin,
            "positions": positions,
            "rebalancing": rebalancing
        }

        all_allocations.append(allocation)

    print("Calculating metrics...")
    metrics = calculate_total_metrics(all_allocations)

    # 리포트 생성
    report = generate_report(all_allocations, metrics)
    print(report)

    # JSON 저장 (날짜 직렬화를 위한 변환)
    save_data = {
        "timestamp": datetime.now().isoformat(),
        "token_prices": token_prices,
        "metrics": metrics,
        "allocations": []
    }

    for allocation in all_allocations:
        save_allocation = {
            **allocation,
            "positions": [
                {**p, "entry_time": p["entry_time"].isoformat()}
                for p in allocation["positions"]
            ],
            "rebalancing": [
                {**r, "time": r["time"].isoformat()}
                for r in allocation["rebalancing"]
            ]
        }
        save_data["allocations"].append(save_allocation)

    with open("volume_maximizing_strategy.json", "w") as f:
        json.dump(save_data, f, indent=2)

    print(f"\n📁 Detailed strategy saved to: volume_maximizing_strategy.json")

if __name__ == "__main__":
    asyncio.run(main())