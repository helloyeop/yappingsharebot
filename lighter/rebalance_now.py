#!/usr/bin/env python3
import asyncio
import aiohttp
import json
from collections import defaultdict
from datetime import datetime

# 모든 지갑 주소
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
]

async def fetch_current_state():
    """현재 상태 조회 및 분석"""

    addresses = [w["addr"] for w in ALL_WALLETS]

    async with aiohttp.ClientSession() as session:
        # 포지션 조회
        data = {"addresses": addresses}
        async with session.post("http://localhost:8000/api/fetch_accounts", json=data) as response:
            result = await response.json()

        # 시장 가격 조회
        async with session.get("http://localhost:8000/api/market_prices") as response:
            market_prices = await response.json()

    return result, market_prices

def analyze_positions(portfolio_data, market_prices):
    """포지션 분석"""

    total_long_exposure = defaultdict(float)
    total_short_exposure = defaultdict(float)
    wallet_info = {}

    # 각 지갑 분석
    for account in portfolio_data.get("accounts", []):
        address = account["l1_address"]
        wallet_num = next((w["num"] for w in ALL_WALLETS if w["addr"] == address), 0)

        available_balance = float(account.get("available_balance", 0))
        collateral = float(account.get("collateral", 0))
        positions = account.get("positions", [])

        # 사용된 마진 계산
        used_margin = 0
        position_list = []

        for pos in positions:
            token = pos.get("symbol", "Unknown")
            side = "LONG" if pos.get("sign", 1) == 1 else "SHORT"
            amount = float(pos.get("position", 0))
            current = float(pos.get("current_price", 0))
            exposure = abs(amount * current)

            # 마진 계산 (position_value / leverage)
            position_value = float(pos.get("position_value", 0))
            leverage_str = pos.get("leverage", "3.0x")
            leverage = float(leverage_str.replace("x", ""))
            margin = position_value / leverage if leverage > 0 else 0
            used_margin += margin

            position_list.append({
                "token": token,
                "side": side,
                "exposure": exposure
            })

            # 총 익스포저 계산
            if side == "LONG":
                total_long_exposure[token] += exposure
            else:
                total_short_exposure[token] += exposure

        # 사용 가능한 마진
        max_margin = collateral * 0.85  # 담보의 85%까지 사용
        available_margin = max(0, max_margin - used_margin)

        wallet_info[wallet_num] = {
            "address": address,
            "collateral": collateral,
            "available_margin": available_margin,
            "used_margin": used_margin,
            "positions": position_list,
            "has_positions": len(position_list) > 0
        }

    # 넷 익스포저 계산
    net_exposure = {}
    imbalances = []

    for token in set(list(total_long_exposure.keys()) + list(total_short_exposure.keys())):
        long = total_long_exposure.get(token, 0)
        short = total_short_exposure.get(token, 0)
        net = long - short
        net_exposure[token] = net

        if abs(net) > 50:  # 50달러 이상 불균형만
            imbalances.append({
                "token": token,
                "long": long,
                "short": short,
                "net": net,
                "abs_net": abs(net)
            })

    # 불균형 정렬 (큰 것부터)
    imbalances.sort(key=lambda x: x["abs_net"], reverse=True)

    return wallet_info, imbalances, total_long_exposure, total_short_exposure

def generate_rebalancing_orders(wallet_info, imbalances):
    """리밸런싱 주문 생성"""

    orders = []

    # 사용 가능한 지갑 찾기
    available_wallets = [
        (num, info) for num, info in wallet_info.items()
        if info["available_margin"] > 10
    ]
    available_wallets.sort(key=lambda x: x[1]["available_margin"], reverse=True)

    # 각 불균형에 대해 주문 생성
    for imbalance in imbalances[:5]:  # 상위 5개만 처리
        token = imbalance["token"]
        net = imbalance["net"]

        # 필요한 액션 결정
        if net > 0:  # Long이 과다
            action = "SHORT"
            target_amount = min(abs(net) * 0.5, 100)  # 50% 조정, 최대 100
        else:  # Short이 과다
            action = "LONG"
            target_amount = min(abs(net) * 0.5, 100)

        # 적절한 지갑 찾기
        for wallet_num, wallet in available_wallets:
            if wallet["available_margin"] < 20:
                continue

            # 이미 같은 토큰의 반대 포지션이 있으면 스킵
            has_opposite = any(
                p["token"] == token and p["side"] != action
                for p in wallet["positions"]
            )
            if has_opposite:
                continue

            # 주문 크기 결정 (마진 기준)
            margin_size = min(
                target_amount / 3,  # 3x 레버리지
                wallet["available_margin"] * 0.5,  # 가용 마진의 50%
                50  # 최대 50달러
            )

            if margin_size >= 10:  # 최소 10달러
                orders.append({
                    "wallet_num": wallet_num,
                    "wallet_addr": wallet["address"],
                    "token": token,
                    "side": action,
                    "margin": round(margin_size, 2),
                    "leverage": 3,
                    "notional": round(margin_size * 3, 2)
                })

                # 이 지갑의 가용 마진 업데이트
                wallet["available_margin"] -= margin_size
                target_amount -= margin_size * 3

                if target_amount <= 0:
                    break

    return orders

def print_report(wallet_info, imbalances, orders):
    """리포트 출력"""

    print("\n" + "="*80)
    print("🎯 IMMEDIATE REBALANCING REPORT")
    print("="*80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 불균형 요약
    print("\n📊 CURRENT IMBALANCES:")
    print("-"*60)
    total_imbalance = sum(i["abs_net"] for i in imbalances)

    for imb in imbalances[:5]:
        symbol = "🔴" if imb["net"] > 0 else "🟢"
        action = "Need SHORT" if imb["net"] > 0 else "Need LONG"
        print(f"{symbol} {imb['token']:6} | Net: ${imb['net']:+8.2f} | {action}")

    print(f"\n⚖️  Total Imbalance: ${total_imbalance:.2f}")
    print(f"   Delta Score: {max(0, 100 - total_imbalance/10):.1f}/100")

    # 사용 가능한 지갑
    print("\n💰 AVAILABLE WALLETS FOR REBALANCING:")
    print("-"*60)

    available_wallets = [
        (num, info) for num, info in wallet_info.items()
        if info["available_margin"] > 10
    ]
    available_wallets.sort(key=lambda x: x[1]["available_margin"], reverse=True)

    for wallet_num, wallet in available_wallets[:8]:
        print(f"Wallet {wallet_num:2} | Available: ${wallet['available_margin']:6.2f} | "
              f"Collateral: ${wallet['collateral']:6.2f}")

    # 리밸런싱 주문
    print("\n" + "="*80)
    print("📝 REBALANCING ORDERS TO EXECUTE NOW:")
    print("="*80)

    if not orders:
        print("❌ No rebalancing possible with current margins")
        return

    total_margin_needed = sum(o["margin"] for o in orders)
    total_notional = sum(o["notional"] for o in orders)

    print(f"\nSummary:")
    print(f"  • Total Orders: {len(orders)}")
    print(f"  • Total Margin Required: ${total_margin_needed:.2f}")
    print(f"  • Total Notional Volume: ${total_notional:.2f}")

    print("\n🔸 EXECUTE THESE ORDERS:")
    print("-"*60)

    for i, order in enumerate(orders, 1):
        print(f"\n{i}. Wallet {order['wallet_num']:2} ({order['wallet_addr'][-10:]})")
        print(f"   ➜ {order['side']:5} {order['token']:6} | "
              f"Margin: ${order['margin']:6.2f} @ {order['leverage']}x | "
              f"Notional: ${order['notional']:7.2f}")

    print("\n" + "="*80)
    print("⚠️  EXECUTION NOTES:")
    print("-"*60)
    print("1. Check market liquidity before executing")
    print("2. Use limit orders to minimize slippage")
    print("3. Wait 30 seconds between orders")
    print("4. Monitor positions after each execution")
    print("="*80)

    # JSON 저장
    save_data = {
        "timestamp": datetime.now().isoformat(),
        "total_imbalance": total_imbalance,
        "orders": orders
    }

    with open("rebalance_orders.json", "w") as f:
        json.dump(save_data, f, indent=2)

    print("\n📁 Orders saved to: rebalance_orders.json")

async def main():
    """메인 실행"""

    print("🔄 Fetching current positions...")
    portfolio_data, market_prices = await fetch_current_state()

    print("📊 Analyzing imbalances...")
    wallet_info, imbalances, long_exp, short_exp = analyze_positions(portfolio_data, market_prices)

    print("🎯 Generating rebalancing orders...")
    orders = generate_rebalancing_orders(wallet_info, imbalances)

    print_report(wallet_info, imbalances, orders)

if __name__ == "__main__":
    asyncio.run(main())