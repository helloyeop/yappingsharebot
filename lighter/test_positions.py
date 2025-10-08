#!/usr/bin/env python3
import asyncio
import aiohttp
import json

async def test_api():
    # 테스트할 지갑 주소 (일부)
    test_addresses = [
        "0x8b49af69dF8d44C735812D30A3A5c66BA6fc05Fc",  # Wallet 6
        "0x7878AE8C54227440293a0BB83b63F39DC24A0899",  # Wallet 3
        "0x497506194d1Bc5D02597142D5A79D9198200118E",  # Wallet 9
    ]

    async with aiohttp.ClientSession() as session:
        # API 테스트
        print("Testing API with addresses:")
        for addr in test_addresses:
            print(f"  - {addr}")

        data = {"addresses": test_addresses}

        try:
            async with session.post("http://localhost:8000/api/fetch_accounts", json=data) as response:
                result = await response.json()

                print(f"\n✅ API Response Status: {response.status}")
                print(f"Number of accounts returned: {len(result.get('accounts', []))}")

                # 각 계정 상세 확인
                for account in result.get("accounts", []):
                    print(f"\n📊 Account: {account['l1_address'][-10:]}")
                    print(f"  Available Balance: {account.get('available_balance', 'N/A')}")
                    print(f"  Collateral: {account.get('collateral', 'N/A')}")
                    print(f"  Positions: {len(account.get('positions', []))}")

                    # 포지션 상세
                    for i, pos in enumerate(account.get("positions", []), 1):
                        print(f"\n    Position {i}:")
                        print(f"      Token: {pos.get('name', 'UNKNOWN')}")
                        print(f"      Side: {'LONG' if pos.get('sign', 1) == 1 else 'SHORT'}")
                        print(f"      Amount: {pos.get('net_amount', 0)}")
                        print(f"      Entry: {pos.get('average_entry', 0)}")
                        print(f"      Current: {pos.get('current_price', 0)}")
                        print(f"      PnL: {pos.get('unrealized_pnl', 0)}")
                        print(f"      PnL %: {pos.get('pnl_percent', 0)}")

                # 시장 가격 테스트
                print("\n" + "="*50)
                print("Testing Market Prices API...")
                async with session.get("http://localhost:8000/api/market_prices") as price_response:
                    prices = await price_response.json()
                    print(f"✅ Market Prices Status: {price_response.status}")
                    print(f"Number of tokens: {len(prices)}")

                    # 일부 가격 표시
                    for token in ["APEX", "STBL", "ZEC", "FF", "0G", "2Z", "EDEN"]:
                        if token in prices:
                            price_info = prices[token]
                            print(f"  {token}: ${price_info.get('last_price', 0):.4f}")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            print(f"Error type: {type(e)}")

asyncio.run(test_api())