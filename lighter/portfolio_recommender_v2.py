#!/usr/bin/env python3
import asyncio
import aiohttp
import json
import random
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta

# 새로운 페어 목록
NEW_PAIRS = ["APEX", "STBL", "ZEC", "FF", "0G", "2Z", "EDEN"]

# 지갑별 실제 담보 금액 (portfolio_analysis_report.json 기준)
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
    {"address": "0x4007Fb7b726111153C07db0B3f1f561F8bad9853", "collateral": 10.0, "index": 17}  # 추정값
]

async def fetch_market_data():
    """현재 시장 데이터 가져오기"""
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:8000/api/market_prices") as response:
            return await response.json()

def calculate_position_size(collateral: float, leverage: int, allocation_percent: float = 0.4) -> float:
    """담보와 레버리지를 기준으로 포지션 크기 계산

    Args:
        collateral: 사용 가능한 담보
        leverage: 레버리지 (정수)
        allocation_percent: 담보 중 사용할 비율 (기본 40%)

    Returns:
        포지션 크기
    """
    # 담보의 일부만 사용 (리스크 관리)
    usable_collateral = collateral * allocation_percent
    # 포지션 크기 = 담보 / 레버리지 (마진 요구사항)
    position_size = usable_collateral

    # 소수점 둘째자리까지, 약간의 랜덤성 추가
    position_size = position_size * random.uniform(0.85, 1.15)
    return round(position_size, 2)

def generate_portfolio_allocation(market_data: Dict) -> List[Dict]:
    """각 지갑의 담보에 맞는 포트폴리오 생성"""

    allocations = []

    # 토큰 가격 정보 수집
    token_prices = {}
    for token in NEW_PAIRS:
        if token in market_data:
            token_prices[token] = market_data[token].get("last_price", 1)

    # 지갑을 그룹으로 나누기
    # 그룹 1: 소액 담보 (< 30 USD) - 단일 포지션, 낮은 레버리지
    small_wallets = [w for w in WALLET_INFO if w["collateral"] < 30]

    # 그룹 2: 중간 담보 (30-100 USD) - 2개 포지션, 중간 레버리지
    medium_wallets = [w for w in WALLET_INFO if 30 <= w["collateral"] < 100]

    # 그룹 3: 대액 담보 (>= 100 USD) - 2-3개 포지션, 다양한 레버리지
    large_wallets = [w for w in WALLET_INFO if w["collateral"] >= 100]

    # 소액 지갑 처리
    for i, wallet in enumerate(small_wallets):
        positions = []

        # 단일 포지션만
        token = NEW_PAIRS[i % len(NEW_PAIRS)]
        side = "LONG" if i % 2 == 0 else "SHORT"
        leverage = random.choice([2, 3])  # 낮은 레버리지

        # 담보의 60% 사용
        position_size = calculate_position_size(wallet["collateral"], leverage, 0.6)

        positions.append({
            "token": token,
            "side": side,
            "size": position_size,
            "leverage": leverage,
            "entry_time": datetime.now() + timedelta(
                hours=random.randint(1, 48),
                minutes=random.randint(0, 59)
            )
        })

        allocations.append({
            "wallet": wallet["address"],
            "wallet_index": wallet["index"],
            "collateral": wallet["collateral"],
            "group": "SMALL",
            "positions": positions,
            "total_margin_used": sum(p["size"] for p in positions)
        })

    # 중간 지갑 처리
    for i, wallet in enumerate(medium_wallets):
        positions = []

        # 2개 포지션 (메인 + 헷지)
        main_token = NEW_PAIRS[i % len(NEW_PAIRS)]
        hedge_token = NEW_PAIRS[(i + 3) % len(NEW_PAIRS)]

        # 메인 포지션
        main_leverage = random.choice([3, 4, 5])
        main_size = calculate_position_size(wallet["collateral"], main_leverage, 0.35)

        positions.append({
            "token": main_token,
            "side": "LONG" if i % 2 == 0 else "SHORT",
            "size": main_size,
            "leverage": main_leverage,
            "entry_time": datetime.now() + timedelta(
                hours=i * 3,
                minutes=random.randint(0, 59)
            )
        })

        # 헷지 포지션
        hedge_leverage = random.choice([2, 3, 4])
        hedge_size = calculate_position_size(wallet["collateral"], hedge_leverage, 0.25)

        positions.append({
            "token": hedge_token,
            "side": "SHORT" if i % 2 == 0 else "LONG",
            "size": hedge_size,
            "leverage": hedge_leverage,
            "entry_time": datetime.now() + timedelta(
                hours=i * 3 + 2,
                minutes=random.randint(0, 59)
            )
        })

        allocations.append({
            "wallet": wallet["address"],
            "wallet_index": wallet["index"],
            "collateral": wallet["collateral"],
            "group": "MEDIUM",
            "positions": positions,
            "total_margin_used": sum(p["size"] for p in positions)
        })

    # 대액 지갑 처리
    for i, wallet in enumerate(large_wallets):
        positions = []

        # 2-3개 포지션
        num_positions = random.choice([2, 3])
        used_tokens = []

        for j in range(num_positions):
            # 중복되지 않는 토큰 선택
            available_tokens = [t for t in NEW_PAIRS if t not in used_tokens]
            if not available_tokens:
                available_tokens = NEW_PAIRS

            token = random.choice(available_tokens)
            used_tokens.append(token)

            # 포지션별로 다른 할당 비율
            if j == 0:  # 메인 포지션
                allocation = 0.3
                leverage = random.choice([4, 5, 6])
            elif j == 1:  # 서브 포지션
                allocation = 0.25
                leverage = random.choice([3, 4, 5])
            else:  # 추가 헷지
                allocation = 0.15
                leverage = random.choice([2, 3])

            size = calculate_position_size(wallet["collateral"], leverage, allocation)
            side = "LONG" if (i + j) % 2 == 0 else "SHORT"

            positions.append({
                "token": token,
                "side": side,
                "size": size,
                "leverage": leverage,
                "entry_time": datetime.now() + timedelta(
                    days=random.randint(0, 2),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59)
                )
            })

        allocations.append({
            "wallet": wallet["address"],
            "wallet_index": wallet["index"],
            "collateral": wallet["collateral"],
            "group": "LARGE",
            "positions": positions,
            "total_margin_used": sum(p["size"] for p in positions)
        })

    return allocations, token_prices

def calculate_portfolio_metrics(allocations: List[Dict], token_prices: Dict) -> Dict:
    """포트폴리오 메트릭 계산"""

    total_long_exposure = {}
    total_short_exposure = {}

    for allocation in allocations:
        for position in allocation["positions"]:
            token = position["token"]
            # 익스포저 = 포지션 크기 * 레버리지
            exposure = position["size"] * position["leverage"]

            if position["side"] == "LONG":
                total_long_exposure[token] = total_long_exposure.get(token, 0) + exposure
            else:
                total_short_exposure[token] = total_short_exposure.get(token, 0) + exposure

    # 델타 계산
    net_exposure = {}
    for token in set(list(total_long_exposure.keys()) + list(total_short_exposure.keys())):
        long = total_long_exposure.get(token, 0)
        short = total_short_exposure.get(token, 0)
        net_exposure[token] = long - short

    total_net_delta = sum(net_exposure.values())
    total_long = sum(total_long_exposure.values())
    total_short = sum(total_short_exposure.values())

    return {
        "long_exposure": total_long_exposure,
        "short_exposure": total_short_exposure,
        "net_exposure": net_exposure,
        "total_net_delta": total_net_delta,
        "total_long": total_long,
        "total_short": total_short,
        "delta_ratio": total_long / total_short if total_short > 0 else float('inf'),
        "delta_neutral_score": 100 - min(100, abs(total_net_delta) / 10)
    }

def generate_report(allocations: List[Dict], token_prices: Dict, metrics: Dict) -> str:
    """포트폴리오 추천 리포트 생성"""

    report = []
    report.append("\n" + "="*80)
    report.append("REALISTIC DELTA-NEUTRAL PORTFOLIO RECOMMENDATION")
    report.append("="*80)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Target Pairs: {', '.join(NEW_PAIRS)}")

    # 토큰 가격
    report.append(f"\n📊 CURRENT PRICES")
    for token, price in token_prices.items():
        report.append(f"  {token}: ${price:.4f}")

    # 포트폴리오 메트릭
    report.append(f"\n⚖️ PORTFOLIO METRICS")
    report.append(f"  Delta Neutrality Score: {metrics['delta_neutral_score']:.1f}/100")
    report.append(f"  Total Net Delta: ${metrics['total_net_delta']:.2f}")
    report.append(f"  Long/Short Ratio: {metrics['delta_ratio']:.2f}")
    report.append(f"  Total Long Exposure: ${metrics['total_long']:.2f}")
    report.append(f"  Total Short Exposure: ${metrics['total_short']:.2f}")

    report.append(f"\n  Token Exposure:")
    for token in NEW_PAIRS:
        if token in metrics['net_exposure']:
            net = metrics['net_exposure'][token]
            long = metrics['long_exposure'].get(token, 0)
            short = metrics['short_exposure'].get(token, 0)
            symbol = "🟢" if net > 0 else "🔴" if net < 0 else "⚪"
            report.append(f"    {symbol} {token}: Net ${net:.2f} (L: ${long:.2f} / S: ${short:.2f})")

    # 지갑별 할당
    report.append(f"\n📋 WALLET ALLOCATIONS BY GROUP")

    for group_name in ["SMALL", "MEDIUM", "LARGE"]:
        group_wallets = [a for a in allocations if a["group"] == group_name]
        if group_wallets:
            report.append(f"\n  [{group_name} COLLATERAL WALLETS]")
            for allocation in group_wallets:
                report.append(f"\n    Wallet {allocation['wallet_index']} ({allocation['wallet'][:10]}...):")
                report.append(f"      Collateral: ${allocation['collateral']:.2f}")
                report.append(f"      Margin Used: ${allocation['total_margin_used']:.2f}")
                report.append(f"      Positions:")
                for pos in allocation["positions"]:
                    report.append(f"        • {pos['side']} {pos['token']}: ${pos['size']:.2f} @ {pos['leverage']}x")
                    report.append(f"          Entry: {pos['entry_time'].strftime('%m/%d %H:%M')}")

    # 실행 가이드
    report.append(f"\n🎯 EXECUTION GUIDELINES")
    report.append("  1. POSITION SIZING: Based on actual wallet collateral")
    report.append("  2. LEVERAGE: Integer values only (2x-6x range)")
    report.append("  3. MARGIN USAGE: Max 70% of available collateral")
    report.append("  4. TIMING: Stagger entries as specified")
    report.append("  5. REBALANCING: When net delta exceeds 10% of total exposure")

    # 리스크 관리
    report.append(f"\n⚠️ RISK MANAGEMENT")
    report.append("  • Stop Loss: -20% per position")
    report.append("  • Take Profit: +25% partial (50% of position)")
    report.append("  • Max Drawdown: 30% of collateral")
    report.append("  • Daily monitoring and rebalancing required")

    # 상관관계 은폐
    report.append(f"\n🔒 CORRELATION MASKING")
    report.append("  • Entry times spread across 48+ hours")
    report.append("  • Position sizes vary by ±15%")
    report.append("  • Different leverage per wallet")
    report.append("  • Mixed token selection patterns")

    report.append("\n" + "="*80)

    return "\n".join(report)

async def main():
    """메인 실행 함수"""

    print("Fetching market data...")
    market_data = await fetch_market_data()

    print("Generating portfolio allocations based on actual collateral...")
    allocations, token_prices = generate_portfolio_allocation(market_data)

    print("Calculating portfolio metrics...")
    metrics = calculate_portfolio_metrics(allocations, token_prices)

    # 리포트 생성
    report = generate_report(allocations, token_prices, metrics)
    print(report)

    # JSON으로 저장
    save_data = {
        "timestamp": datetime.now().isoformat(),
        "token_prices": token_prices,
        "allocations": [
            {
                **a,
                "positions": [
                    {**p, "entry_time": p["entry_time"].isoformat()}
                    for p in a["positions"]
                ]
            }
            for a in allocations
        ],
        "metrics": metrics
    }

    with open("portfolio_recommendation_v2.json", "w") as f:
        json.dump(save_data, f, indent=2)

    print(f"\n📁 Detailed recommendation saved to: portfolio_recommendation_v2.json")

if __name__ == "__main__":
    asyncio.run(main())