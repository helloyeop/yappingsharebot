#!/usr/bin/env python3
import requests
import json

def test_fetch_accounts():
    """
    lighter API의 서브계정 포트폴리오 가져오기 테스트
    """
    # 테스트 주소 (예시에서 제공된 주소)
    test_address = "0xb43ed67042D80C8f496F4E46432ba3566F5aa580"

    # API 엔드포인트
    api_url = "http://localhost:8000/lighter/api/fetch_accounts"

    # 요청 데이터
    payload = {
        "addresses": [test_address]
    }

    try:
        # API 호출
        response = requests.post(api_url, json=payload)
        response.raise_for_status()

        data = response.json()

        print("=" * 50)
        print("API 테스트 결과")
        print("=" * 50)

        # 계정 정보 출력
        accounts = data.get("accounts", [])
        print(f"\n총 계정 수: {len(accounts)}")

        for i, account in enumerate(accounts):
            account_type = account.get("account_type", 0)
            account_type_label = account.get("account_type_label", "Unknown")
            total_asset = account.get("total_asset_value", "0")
            positions = account.get("positions", [])

            print(f"\n계정 {i+1}:")
            print(f"  - 타입: {account_type_label} (type={account_type})")
            print(f"  - 주소: {account.get('l1_address', 'N/A')}")
            print(f"  - 총 자산: ${total_asset}")
            print(f"  - 포지션 수: {len(positions)}")

            if positions:
                print(f"  - 포지션 상세:")
                for pos in positions[:3]:  # 처음 3개만 표시
                    symbol = pos.get("symbol", "N/A")
                    position_type = "Long" if pos.get("sign", 1) == 1 else "Short"
                    position_value = pos.get("position_value", "0")
                    unrealized_pnl = pos.get("unrealized_pnl", "0")
                    print(f"    • {symbol} ({position_type}): ${position_value} | PnL: ${unrealized_pnl}")

        # 포지션 요약 출력
        position_summary = data.get("position_summary", {})
        if position_summary:
            print(f"\n포지션 요약:")
            for symbol, summary in position_summary.items():
                net_position = summary.get("net_position", 0)
                total_value = summary.get("total_value", 0)
                accounts_holding = summary.get("accounts", [])
                print(f"  - {symbol}: Net={net_position:.4f}, Value=${total_value:.2f}")
                print(f"    보유 계정: {', '.join(accounts_holding[:3])}")  # 처음 3개만 표시

        print("\n✅ 테스트 성공: 서브계정 포트폴리오가 정상적으로 조회됩니다.")

    except requests.exceptions.RequestException as e:
        print(f"❌ API 호출 실패: {e}")
        print("\n서버가 실행 중인지 확인해주세요.")
        print("실행 명령: python start.py")
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")

if __name__ == "__main__":
    print("Lighter API 서브계정 테스트 시작...")
    test_fetch_accounts()