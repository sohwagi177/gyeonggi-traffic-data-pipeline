import os
import time
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import requests
from dotenv import load_dotenv

# 동기 수집 코드에서 이미 만든 기능 재사용
from sync_collect import FIELDS, get_link_ids, get_traffic


# ① 배치 설정
BATCH_SIZE = 20   # 한 배치당 최대 20개
BATCH_DELAY = 1   # 배치 사이 1초 대기

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "data" / "raw"


def chunks(data, size):
    """② 데이터를 size개씩 잘라서 반환"""
    for i in range(0, len(data), size):
        yield data[i:i + size]


def main():
    # ③ .env에서 API Key 불러오기
    load_dotenv(BASE_DIR / ".env")
    service_key = unquote(os.getenv("SERVICE_KEY", "").strip())

    if not service_key:
        raise ValueError(".env 파일에 SERVICE_KEY가 없습니다.")

    start_time = time.perf_counter()

    records = []
    no_data = []
    failed = []

    with requests.Session() as session:
        # ④ 전체 linkId 조회
        link_ids = get_link_ids(session, service_key)

        # ⑤ 20개씩 배치로 나누기
        batches = list(chunks(link_ids, BATCH_SIZE))

        print(f"전체 구간: {len(link_ids)}개")
        print(f"배치 크기: {BATCH_SIZE}개")
        print(f"전체 배치: {len(batches)}개\n")

        # ⑥ 배치별로 순서대로 수집
        for batch_num, batch in enumerate(batches, start=1):
            print(
                f"===== 배치 {batch_num}/{len(batches)} "
                f"({len(batch)}개) ====="
            )

            for link_id in batch:
                try:
                    traffic = get_traffic(
                        session,
                        service_key,
                        link_id,
                    )

                    if traffic:
                        records.append(traffic)
                        print(f"{link_id} 수집 성공")
                    else:
                        no_data.append(link_id)
                        print(f"{link_id} 데이터 없음")

                except Exception as error:
                    failed.append(link_id)
                    print(f"{link_id} 수집 실패: {error}")

            # ⑦ 마지막 배치가 아니면 잠시 대기
            if batch_num < len(batches):
                print(f"{BATCH_DELAY}초 대기\n")
                time.sleep(BATCH_DELAY)

    # ⑧ 모든 배치 결과를 CSV 하나로 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = (
        OUTPUT_DIR
        / f"bundang_suseo_batch_{timestamp}.csv"
    )

    pd.DataFrame(
        records,
        columns=FIELDS.keys(),
    ).to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    elapsed = time.perf_counter() - start_time

    # ⑨ 최종 결과
    print("\n" + "=" * 50)
    print(f"CSV 저장 완료: {output_path}")
    print(f"전체 구간: {len(link_ids)}건")
    print(f"전체 배치: {len(batches)}개")
    print(f"수집 성공: {len(records)}건")
    print(f"데이터 없음: {len(no_data)}건")
    print(f"요청 실패: {len(failed)}건")
    print(f"전체 실행시간: {elapsed:.2f}초")


if __name__ == "__main__":
    main()