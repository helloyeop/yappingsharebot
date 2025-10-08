#!/usr/bin/env python3
import asyncio
import aiohttp
import json

async def debug_api():
    # 테스트 지갑 (포지션이 있는 것으로 알려진 지갑)
    test_address = "0x8b49af69dF8d44C735812D30A3A5c66BA6fc05Fc"  # Wallet 6

    async with aiohttp.ClientSession() as session:
        print("🔍 Debugging API Response Structure\n")
        print(f"Testing with wallet: {test_address}\n")

        data = {"addresses": [test_address]}

        async with session.post("http://localhost:8000/api/fetch_accounts", json=data) as response:
            result = await response.json()

            if result.get("accounts") and len(result["accounts"]) > 0:
                account = result["accounts"][0]

                print("📊 Account Structure:")
                print(f"  Keys: {list(account.keys())}\n")

                # 포지션 상세 분석
                positions = account.get("positions", [])
                print(f"📈 Positions: {len(positions)} found\n")

                if positions:
                    print("First Position Complete Structure:")
                    print("="*50)
                    first_pos = positions[0]

                    # 모든 필드 출력
                    for key, value in first_pos.items():
                        print(f"  {key}: {value} (type: {type(value).__name__})")

                    print("\n" + "="*50)
                    print("\nKey Fields Analysis:")
                    print(f"  'name' field: {first_pos.get('name', 'NOT FOUND')}")
                    print(f"  'symbol' field: {first_pos.get('symbol', 'NOT FOUND')}")
                    print(f"  'position' field: {first_pos.get('position', 'NOT FOUND')}")
                    print(f"  'net_amount' field: {first_pos.get('net_amount', 'NOT FOUND')}")
                    print(f"  'size' field: {first_pos.get('size', 'NOT FOUND')}")
                    print(f"  'quantity' field: {first_pos.get('quantity', 'NOT FOUND')}")
                    print(f"  'sign' field: {first_pos.get('sign', 'NOT FOUND')}")
                    print(f"  'side' field: {first_pos.get('side', 'NOT FOUND')}")

                    # 모든 포지션 요약
                    print("\n" + "="*50)
                    print("All Positions Summary:")
                    for i, pos in enumerate(positions, 1):
                        symbol = pos.get('symbol') or pos.get('name') or 'UNKNOWN'
                        position = pos.get('position') or pos.get('net_amount') or pos.get('size') or 0
                        sign = pos.get('sign', 1)
                        side = "LONG" if sign == 1 else "SHORT"

                        print(f"\n  Position {i}:")
                        print(f"    Symbol/Name: {symbol}")
                        print(f"    Position Value: {position}")
                        print(f"    Side: {side}")
                        print(f"    Available Keys: {list(pos.keys())[:5]}...")  # 처음 5개 키만

                # Raw JSON 저장
                with open("api_response_debug.json", "w") as f:
                    json.dump(result, f, indent=2)
                print(f"\n📁 Full response saved to: api_response_debug.json")

asyncio.run(debug_api())