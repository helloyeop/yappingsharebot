#!/usr/bin/env python3
import asyncio
import aiohttp
import json
import random
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
import hashlib

# 새로운 페어 목록
NEW_PAIRS = ["APEX", "STBL", "ZEC", "FF", "0G", "2Z", "EDEN"]

# 17개 지갑 주소
WALLET_ADDRESSES = [
    "0xC74Ef16B20c50B7337585a0a8e1eed3EDd50CF43",
    "0xe67b28750153E7D95Ff001b2557EbA6C5F56092c",
    "0x7878AE8C54227440293a0BB83b63F39DC24A0899",
    "0xe5909A5817325797f8Ed2C4c079f6c78B5E9bfa2",
    "0x29855eB076f6d4a571890a75fe8944380ca6ccC6",
    "0x8b49af69dF8d44C735812D30A3A5c66BA6fc05Fc",
    "0xE81261c93c99b4DCE06068adC0C2a7fFE425732f",
    "0x349f3e1db87719CE7c1013AE7b7Feb70053A1c2f",
    "0x497506194d1Bc5D02597142D5A79D9198200118E",
    "0x25dcd95A7a6D56eA4e781C7586306a4d9768227C",
    "0x51a35979C49354B2eD87F86eb1A679815753c331",
    "0xa9B5be1fc07E0538A5278beedB3A45bb3fbDC893",
    "0x5979857213bb73233aDBf029a7454DFb00A33539",
    "0x9d1cA39386cb3D35c66674aA0Ce41e3403731241",
    "0xFD930dB05F90885DEd7Db693057E5B899b528b2b",
    "0x06d9681C02E2b5182C3489477f4b09D38f3959B2",
    "0x4007Fb7b726111153C07db0B3f1f561F8bad9853"
]

async def fetch_market_data():
    """현재 시장 데이터 가져오기"""
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:8000/api/market_prices") as response:
            return await response.json()

def generate_portfolio_allocation(market_data: Dict, total_capital: float = 1200) -> List[Dict]:
    """델타 중립 포트폴리오 생성"""

    recommendations = []

    # 각 토큰의 현재 가격과 변동성 확인
    token_info = {}
    for token in NEW_PAIRS:
        if token in market_data:
            price_data = market_data[token]
            token_info[token] = {
                "price": price_data.get("last_price", 0),
                "daily_change": price_data.get("daily_change", 0),
                "daily_high": price_data.get("daily_high", 0),
                "daily_low": price_data.get("daily_low", 0),
                "volatility": ((price_data.get("daily_high", 0) - price_data.get("daily_low", 0)) /
                              max(price_data.get("last_price", 1), 0.001)) * 100
            }

    # 지갑별 할당 전략
    wallet_allocations = []

    # 그룹 1: APEX 중심 전략 (Wallets 1-4)
    group1_tokens = ["APEX", "STBL", "ZEC"]
    for i in range(4):
        wallet = WALLET_ADDRESSES[i]
        positions = []

        # 메인 포지션
        main_token = group1_tokens[i % len(group1_tokens)]
        hedge_token = group1_tokens[(i + 1) % len(group1_tokens)]

        # 포지션 크기 랜덤화 (상관관계 은폐)
        base_size = 50 + random.uniform(-15, 15)
        leverage = round(random.uniform(2.3, 4.7), 1)

        positions.append({
            "token": main_token,
            "side": "LONG" if i % 2 == 0 else "SHORT",
            "size": round(base_size * random.uniform(0.9, 1.1), 2),
            "leverage": leverage,
            "entry_time": datetime.now() + timedelta(hours=i*2, minutes=random.randint(0, 59))
        })

        # 헷지 포지션
        positions.append({
            "token": hedge_token,
            "side": "SHORT" if i % 2 == 0 else "LONG",
            "size": round(base_size * 0.7 * random.uniform(0.85, 1.15), 2),
            "leverage": round(leverage * 0.8, 1),
            "entry_time": datetime.now() + timedelta(hours=i*2+1, minutes=random.randint(0, 59))
        })

        wallet_allocations.append({
            "wallet": wallet,
            "wallet_index": i + 1,
            "group": "APEX_GROUP",
            "positions": positions,
            "total_exposure": sum(p["size"] * p["leverage"] for p in positions)
        })

    # 그룹 2: FF/0G 페어 트레이딩 (Wallets 5-8)
    group2_tokens = ["FF", "0G", "EDEN"]
    for i in range(4, 8):
        wallet = WALLET_ADDRESSES[i]
        positions = []

        # 페어 트레이딩 전략
        if i % 2 == 0:
            # FF Long, 0G Short
            positions.append({
                "token": "FF",
                "side": "LONG",
                "size": round(60 * random.uniform(0.8, 1.2), 2),
                "leverage": round(random.uniform(1.5, 3.5), 1),
                "entry_time": datetime.now() + timedelta(hours=(i-4)*3, minutes=random.randint(0, 59))
            })
            positions.append({
                "token": "0G",
                "side": "SHORT",
                "size": round(45 * random.uniform(0.9, 1.1), 2),
                "leverage": round(random.uniform(2.0, 4.0), 1),
                "entry_time": datetime.now() + timedelta(hours=(i-4)*3+2, minutes=random.randint(0, 59))
            })
        else:
            # 0G Long, FF Short
            positions.append({
                "token": "0G",
                "side": "LONG",
                "size": round(55 * random.uniform(0.85, 1.15), 2),
                "leverage": round(random.uniform(2.5, 4.5), 1),
                "entry_time": datetime.now() + timedelta(hours=(i-4)*4, minutes=random.randint(0, 59))
            })
            positions.append({
                "token": "FF",
                "side": "SHORT",
                "size": round(48 * random.uniform(0.9, 1.1), 2),
                "leverage": round(random.uniform(1.8, 3.2), 1),
                "entry_time": datetime.now() + timedelta(hours=(i-4)*4+1, minutes=random.randint(0, 59))
            })

        # EDEN을 추가 헷징용으로 사용
        if random.random() > 0.5:
            positions.append({
                "token": "EDEN",
                "side": random.choice(["LONG", "SHORT"]),
                "size": round(25 * random.uniform(0.7, 1.3), 2),
                "leverage": round(random.uniform(1.2, 2.8), 1),
                "entry_time": datetime.now() + timedelta(hours=(i-4)*5, minutes=random.randint(0, 59))
            })

        wallet_allocations.append({
            "wallet": wallet,
            "wallet_index": i + 1,
            "group": "PAIR_TRADING",
            "positions": positions,
            "total_exposure": sum(p["size"] * p["leverage"] for p in positions)
        })

    # 그룹 3: 2Z/ZEC 볼라틸리티 플레이 (Wallets 9-12)
    group3_tokens = ["2Z", "ZEC", "STBL"]
    for i in range(8, 12):
        wallet = WALLET_ADDRESSES[i]
        positions = []

        # 볼라틸리티 전략
        main_token = group3_tokens[(i-8) % len(group3_tokens)]

        # 메인 포지션 (방향성)
        positions.append({
            "token": main_token,
            "side": "LONG" if (i-8) < 2 else "SHORT",
            "size": round(70 * random.uniform(0.75, 1.25), 2),
            "leverage": round(random.uniform(3.0, 5.5), 1),
            "entry_time": datetime.now() + timedelta(hours=(i-8)*2.5, minutes=random.randint(0, 59))
        })

        # STBL을 안정성 헷지로 사용
        positions.append({
            "token": "STBL",
            "side": "SHORT" if (i-8) < 2 else "LONG",
            "size": round(40 * random.uniform(0.8, 1.2), 2),
            "leverage": round(random.uniform(1.0, 2.0), 1),
            "entry_time": datetime.now() + timedelta(hours=(i-8)*2.5+1.5, minutes=random.randint(0, 59))
        })

        wallet_allocations.append({
            "wallet": wallet,
            "wallet_index": i + 1,
            "group": "VOLATILITY_PLAY",
            "positions": positions,
            "total_exposure": sum(p["size"] * p["leverage"] for p in positions)
        })

    # 그룹 4: 혼합 전략 (Wallets 13-17)
    all_tokens = NEW_PAIRS
    for i in range(12, 17):
        wallet = WALLET_ADDRESSES[i]
        positions = []

        # 랜덤하게 2-3개 토큰 선택
        num_positions = random.randint(2, 3)
        selected_tokens = random.sample(all_tokens, num_positions)

        for j, token in enumerate(selected_tokens):
            side = "LONG" if (i + j) % 2 == 0 else "SHORT"
            positions.append({
                "token": token,
                "side": side,
                "size": round(random.uniform(30, 80), 2),
                "leverage": round(random.uniform(1.5, 4.5), 1),
                "entry_time": datetime.now() + timedelta(
                    days=random.randint(0, 2),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59)
                )
            })

        wallet_allocations.append({
            "wallet": wallet,
            "wallet_index": i + 1,
            "group": "MIXED_STRATEGY",
            "positions": positions,
            "total_exposure": sum(p["size"] * p["leverage"] for p in positions)
        })

    return wallet_allocations, token_info

def calculate_portfolio_metrics(allocations: List[Dict], token_info: Dict) -> Dict:
    """포트폴리오 메트릭 계산"""

    total_long_exposure = {}
    total_short_exposure = {}

    for allocation in allocations:
        for position in allocation["positions"]:
            token = position["token"]
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

    return {
        "long_exposure": total_long_exposure,
        "short_exposure": total_short_exposure,
        "net_exposure": net_exposure,
        "total_net_delta": total_net_delta,
        "delta_neutral_score": 100 - min(100, abs(total_net_delta) / 10)  # 0-100 점수
    }

def generate_report(allocations: List[Dict], token_info: Dict, metrics: Dict) -> str:
    """포트폴리오 추천 리포트 생성"""

    report = []
    report.append("\n" + "="*80)
    report.append("DELTA-NEUTRAL PORTFOLIO RECOMMENDATION")
    report.append("="*80)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Target Pairs: {', '.join(NEW_PAIRS)}")

    # 토큰 정보
    report.append(f"\n📊 MARKET ANALYSIS")
    for token, info in token_info.items():
        report.append(f"  {token}:")
        report.append(f"    Price: ${info['price']:.4f}")
        report.append(f"    24h Change: {info['daily_change']:.2f}%")
        report.append(f"    Volatility: {info['volatility']:.2f}%")

    # 포트폴리오 메트릭
    report.append(f"\n⚖️ PORTFOLIO METRICS")
    report.append(f"  Delta Neutrality Score: {metrics['delta_neutral_score']:.1f}/100")
    report.append(f"  Total Net Delta: ${metrics['total_net_delta']:.2f}")

    report.append(f"\n  Token Exposure:")
    for token in NEW_PAIRS:
        if token in metrics['net_exposure']:
            net = metrics['net_exposure'][token]
            long = metrics['long_exposure'].get(token, 0)
            short = metrics['short_exposure'].get(token, 0)
            report.append(f"    {token}: Net ${net:.2f} (Long ${long:.2f} / Short ${short:.2f})")

    # 지갑별 할당
    report.append(f"\n📋 WALLET ALLOCATIONS")

    for group_name in ["APEX_GROUP", "PAIR_TRADING", "VOLATILITY_PLAY", "MIXED_STRATEGY"]:
        group_wallets = [a for a in allocations if a["group"] == group_name]
        if group_wallets:
            report.append(f"\n  [{group_name}]")
            for allocation in group_wallets:
                report.append(f"\n    Wallet {allocation['wallet_index']} ({allocation['wallet'][:10]}...):")
                for pos in allocation["positions"]:
                    report.append(f"      • {pos['side']} {pos['token']}: ${pos['size']:.2f} @ {pos['leverage']}x")
                    report.append(f"        Entry: {pos['entry_time'].strftime('%Y-%m-%d %H:%M')}")

    # 실행 가이드
    report.append(f"\n🎯 EXECUTION GUIDELINES")
    report.append("  1. TIMING: Stagger entries as specified (DO NOT execute all at once)")
    report.append("  2. SIZING: Use exact amounts specified (avoid round numbers)")
    report.append("  3. LEVERAGE: Vary leverage levels as specified")
    report.append("  4. MONITORING: Rebalance when net delta exceeds ±$500")

    # 리스크 관리
    report.append(f"\n⚠️ RISK MANAGEMENT")
    report.append("  • Set stop loss at -15% for each position")
    report.append("  • Take partial profits at +20%")
    report.append("  • Maximum exposure per wallet: 20% of total capital")
    report.append("  • Rebalance daily to maintain delta neutrality")

    report.append("\n" + "="*80)

    return "\n".join(report)

async def main():
    """메인 실행 함수"""

    print("Fetching market data...")
    market_data = await fetch_market_data()

    print("Generating portfolio allocations...")
    allocations, token_info = generate_portfolio_allocation(market_data)

    print("Calculating portfolio metrics...")
    metrics = calculate_portfolio_metrics(allocations, token_info)

    # 리포트 생성
    report = generate_report(allocations, token_info, metrics)
    print(report)

    # JSON으로 저장
    save_data = {
        "timestamp": datetime.now().isoformat(),
        "token_info": token_info,
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

    with open("portfolio_recommendation.json", "w") as f:
        json.dump(save_data, f, indent=2)

    print(f"\n📁 Detailed recommendation saved to: portfolio_recommendation.json")

if __name__ == "__main__":
    asyncio.run(main())