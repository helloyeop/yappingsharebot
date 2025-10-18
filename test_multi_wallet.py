#!/usr/bin/env python3
import requests
import json

def test_multi_wallet():
    """
    여러 지갑 주소와 서브계정 인덱싱 테스트
    """
    # 테스트 주소들 (첫 번째는 실제 주소, 나머지는 가상)
    test_addresses = [
        "0xb43ed67042D80C8f496F4E46432ba3566F5aa580",  # 실제 주소 (메인 + 서브계정들)
        "0x0000000000000000000000000000000000000001",  # 가상 주소 1
        "0x0000000000000000000000000000000000000002",  # 가상 주소 2
    ]

    # API 엔드포인트
    api_url = "http://localhost:8000/lighter/api/fetch_accounts"

    # 요청 데이터
    payload = {
        "addresses": test_addresses
    }

    try:
        # API 호출
        response = requests.post(api_url, json=payload)
        response.raise_for_status()

        data = response.json()

        print("=" * 60)
        print("다중 지갑 주소 인덱싱 테스트")
        print("=" * 60)

        # 계정 정보 출력
        accounts = data.get("accounts", [])
        print(f"\n입력한 지갑 주소 수: {len(test_addresses)}")
        print(f"반환된 총 계정 수: {len(accounts)}")

        # 지갑 주소별로 계정 그룹화
        wallet_groups = {}
        for account in accounts:
            addr = account.get("l1_address", "")
            if addr not in wallet_groups:
                wallet_groups[addr] = []
            wallet_groups[addr].append(account)

        print(f"\n고유 지갑 주소 수: {len(wallet_groups)}")
        print("-" * 60)

        # 각 지갑 그룹 출력
        for wallet_idx, (address, group_accounts) in enumerate(wallet_groups.items(), 1):
            print(f"\n지갑 #{wallet_idx}: {address}")
            print(f"  이 지갑의 계정 수: {len(group_accounts)}")

            for acc in group_accounts:
                account_type = acc.get("account_type", 0)
                account_type_label = acc.get("account_type_label", "Unknown")
                total_asset = acc.get("total_asset_value", "0")
                positions = acc.get("positions", [])

                print(f"    - {account_type_label} (type={account_type})")
                print(f"      총 자산: ${total_asset}")
                print(f"      포지션 수: {len(positions)}")

        print("\n" + "=" * 60)
        print("✅ 인덱싱 테스트 완료")
        print("\n설명:")
        print("- 동일한 지갑 주소의 메인/서브 계정들은 같은 인덱스를 가져야 합니다")
        print("- 서로 다른 지갑 주소는 다른 인덱스를 가져야 합니다")

    except requests.exceptions.RequestException as e:
        print(f"❌ API 호출 실패: {e}")
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")

if __name__ == "__main__":
    print("다중 지갑 주소 인덱싱 테스트 시작...")
    test_multi_wallet()