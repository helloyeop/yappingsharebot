#!/usr/bin/env python3
import asyncio
import aiohttp
import json
from collections import defaultdict

# 모든 지갑 주소
ALL_WALLETS = [
    "0xC74Ef16B20c50B7337585a0a8e1eed3EDd50CF43",  # Wallet 1
    "0xe67b28750153E7D95Ff001b2557EbA6C5F56092c",  # Wallet 2
    "0x7878AE8C54227440293a0BB83b63F39DC24A0899",  # Wallet 3
    "0xe5909A5817325797f8Ed2C4c079f6c78B5E9bfa2",  # Wallet 4
    "0x29855eB076f6d4a571890a75fe8944380ca6ccC6",  # Wallet 5
    "0x8b49af69dF8d44C735812D30A3A5c66BA6fc05Fc",  # Wallet 6
    "0xE81261c93c99b4DCE06068adC0C2a7fFE425732f",  # Wallet 7
    "0x349f3e1db87719CE7c1013AE7b7Feb70053A1c2f",  # Wallet 8
    "0x497506194d1Bc5D02597142D5A79D9198200118E",  # Wallet 9
    "0x25dcd95A7a6D56eA4e781C7586306a4d9768227C",  # Wallet 10
    "0x51a35979C49354B2eD87F86eb1A679815753c331",  # Wallet 11
    "0xa9B5be1fc07E0538A5278beedB3A45bb3fbDC893",  # Wallet 12
    "0x5979857213bb73233aDBf029a7454DFb00A33539",  # Wallet 13
    "0x9d1cA39386cb3D35c66674aA0Ce41e3403731241",  # Wallet 14
    "0xFD930dB05F90885DEd7Db693057E5B899b528b2b",  # Wallet 15
    "0x06d9681C02E2b5182C3489477f4b09D38f3959B2",  # Wallet 16
]

async def check_all_positions():
    """모든 지갑의 현재 포지션 확인"""

    async with aiohttp.ClientSession() as session:
        data = {"addresses": ALL_WALLETS}

        async with session.post("http://localhost:8000/api/fetch_accounts", json=data) as response:
            result = await response.json()

            print("\n" + "="*80)
            print("CURRENT POSITIONS SUMMARY")
            print("="*80)

            total_long_exposure = defaultdict(float)
            total_short_exposure = defaultdict(float)
            wallet_summary = []

            for account in result.get("accounts", []):
                address = account["l1_address"]
                wallet_num = ALL_WALLETS.index(address) + 1 if address in ALL_WALLETS else 0

                positions = account.get("positions", [])

                if positions:
                    wallet_info = {
                        "wallet": wallet_num,
                        "address": address[-10:],
                        "positions": []
                    }

                    for pos in positions:
                        token = pos.get("symbol", "Unknown")
                        side = "LONG" if pos.get("sign", 1) == 1 else "SHORT"
                        amount = float(pos.get("position", 0))
                        current = float(pos.get("current_price", 0))
                        exposure = abs(amount * current)
                        pnl = float(pos.get("unrealized_pnl", 0))

                        wallet_info["positions"].append({
                            "token": token,
                            "side": side,
                            "amount": amount,
                            "exposure": exposure,
                            "pnl": pnl
                        })

                        # 총 익스포저 계산
                        if side == "LONG":
                            total_long_exposure[token] += exposure
                        else:
                            total_short_exposure[token] += exposure

                    wallet_summary.append(wallet_info)

            # 지갑별 포지션 출력
            print("\n📊 WALLET POSITIONS:")
            for wallet in sorted(wallet_summary, key=lambda x: x["wallet"]):
                print(f"\nWallet {wallet['wallet']} (...{wallet['address']}):")
                for pos in wallet["positions"]:
                    symbol = "🟢" if pos["side"] == "LONG" else "🔴"
                    pnl_symbol = "+" if pos["pnl"] > 0 else ""
                    print(f"  {symbol} {pos['side']:5} {pos['token']:6} | "
                          f"Amount: {pos['amount']:8.2f} | "
                          f"Exposure: ${pos['exposure']:10.2f} | "
                          f"PnL: {pnl_symbol}${abs(pos['pnl']):8.2f}")

            # 전체 익스포저 요약
            print("\n" + "="*80)
            print("TOTAL MARKET EXPOSURE:")
            print("="*80)

            all_tokens = set(list(total_long_exposure.keys()) + list(total_short_exposure.keys()))
            for token in sorted(all_tokens):
                long = total_long_exposure.get(token, 0)
                short = total_short_exposure.get(token, 0)
                net = long - short
                symbol = "🟢" if net > 0 else "🔴" if net < 0 else "⚪"
                print(f"{symbol} {token:6} | Long: ${long:10.2f} | Short: ${short:10.2f} | Net: ${net:+10.2f}")

            # 델타 점수
            total_imbalance = sum(abs(total_long_exposure.get(t, 0) - total_short_exposure.get(t, 0)) for t in all_tokens)
            delta_score = max(0, 100 - (total_imbalance / 10))
            print(f"\n⚖️ Delta Neutrality Score: {delta_score:.1f}/100")
            print(f"   Total Imbalance: ${total_imbalance:.2f}")

            # 그룹 제안
            print("\n" + "="*80)
            print("RECOMMENDED GROUPS FOR REBALANCING:")
            print("="*80)

            # 익스포저가 큰 지갑 그룹핑
            high_exposure_wallets = [w for w in wallet_summary if any(p["exposure"] > 100 for p in w["positions"])]
            if high_exposure_wallets:
                print("\n📍 GROUP A (High Exposure):")
                for w in high_exposure_wallets[:4]:
                    print(f"   - Wallet {w['wallet']}")

asyncio.run(check_all_positions())