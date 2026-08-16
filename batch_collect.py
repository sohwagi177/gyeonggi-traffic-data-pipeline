import time

import requests

from traffic import (
    load_service_key,
    save_records,
)

# ① 성남시 대상 LINK_ID와 동기 교통정보 조회 함수 재사용
from sync_collect import (
    load_target_link_ids,
    get_traffic,
)


# ② 배치 설정
BATCH_SIZE = 20
BATCH_DELAY = 1


def main() -> None:
    """③ 성남시 대상 링크를 20개씩 나누어 배치 수집한다."""

    service_key = load_service_key()
    link_ids = load_target_link_ids()

    total = len(link_ids)
    total_batches = (
        total + BATCH_SIZE - 1
    ) // BATCH_SIZE

    start_time = time.perf_counter()

    records = []
    no_data = []
    failed = []

    print(f"성남시 수집 대상: {total}개")
    print(f"배치 크기: {BATCH_SIZE}개")
    print(f"전체 배치: {total_batches}개")
    print(f"배치 사이 대기: {BATCH_DELAY}초\n")

    with requests.Session() as session:

        # ④ 전체 LINK_ID를 20개씩 나누어 처리
        for batch_num, start in enumerate(
            range(0, total, BATCH_SIZE),
            start=1,
        ):
            batch = link_ids[
                start:start + BATCH_SIZE
            ]

            print(
                f"===== 배치 "
                f"{batch_num}/{total_batches} "
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
                        result = "수집 성공"

                    else:
                        no_data.append(link_id)
                        result = "데이터 없음"

                except (
                    requests.RequestException,
                    RuntimeError,
                ) as error:
                    failed.append(link_id)
                    result = (
                        f"수집 실패: {error}"
                    )

                print(
                    f"{link_id} {result}"
                )

            # ⑤ 마지막 배치가 아니면 1초 대기
            if batch_num < total_batches:
                print(
                    f"{BATCH_DELAY}초 대기\n"
                )
                time.sleep(BATCH_DELAY)

    # ⑥ 성남시 배치 결과를 Parquet으로 저장
    output_path = save_records(
        records,
        "batch",
        "seongnam",
    )

    elapsed = (
        time.perf_counter()
        - start_time
    )

    print("\n" + "=" * 50)
    print(f"저장 완료: {output_path}")
    print(f"전체 대상: {total}건")
    print(f"전체 배치: {total_batches}개")
    print(f"수집 성공: {len(records)}건")
    print(f"데이터 없음: {len(no_data)}건")
    print(f"요청 실패: {len(failed)}건")
    print(f"전체 실행시간: {elapsed:.2f}초")

    if failed:
        print(
            "실패한 linkId: "
            + ", ".join(failed)
        )


if __name__ == "__main__":
    main()