#!/usr/bin/env python3
import asyncio
import aiohttp
import json

async def test_api():
    addresses = ["0xC74Ef16B20c50B7337585a0a8e1eed3EDd50CF43"]

    async with aiohttp.ClientSession() as session:
        data = {"addresses": addresses}
        async with session.post("http://localhost:8000/api/fetch_accounts", json=data) as response:
            result = await response.json()
            print(json.dumps(result, indent=2))

            # 구조 확인
            print("\n=== Structure Analysis ===")
            print(f"Type: {type(result)}")
            print(f"Keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")

            if "accounts" in result:
                accounts = result["accounts"]
                if accounts and len(accounts) > 0:
                    print(f"\nFirst account keys: {accounts[0].keys()}")

asyncio.run(test_api())