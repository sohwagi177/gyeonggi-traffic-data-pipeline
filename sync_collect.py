import time
from pathlib import Path

import pandas as pd
import requests

from traffic import (
    TRAFFIC_URL,
    load_service_key,
    parse_xml,
    get_status,
    extract_traffic,
    save_records,
)


# ① 성남시 수집 대상 링크 파일
BASE_DIR = Path(__file__).resolve().parent

TARGET_PATH = (
    BASE_DIR
    / "data"
    / "reference"
    / "seongnam_target_links.parquet"
)


def load_target_link_ids() -> list[str]:
    """② 성남시 수집 대상 LINK_ID를 불러온다."""

    if not TARGET_PATH.exists():
        raise FileNotFoundError(
            f"수집 대상 파일이 없습니다: {TARGET_PATH}"
        )

    df = pd.read_parquet(TARGET_PATH)

    link_ids = (
        df["LINK_ID"]
        .astype(str)
        .str.strip()
        .drop_duplicates()
        .tolist()
    )

    return link_ids


def get_xml(
    session: requests.Session,
    url: str,
    params: dict[str, str],
):
    """③ 동기 방식으로 API를 호출한다."""

    response = session.get(
        url,
        params=params,
        timeout=20,
    )
    response.raise_for_status()

    return parse_xml(response.content)


def get_traffic(
    session: requests.Session,
    service_key: str,
    link_id: str,
) -> dict[str, str] | None:
    """④ linkId 한 개의 최신 교통정보를 조회한다."""

    root = get_xml(
        session,
        TRAFFIC_URL,
        {
            "serviceKey": service_key,
            "linkId": link_id,
        },
    )

    code, message = get_status(root)

    if code == "4":
        return None

    if code != "0":
        raise RuntimeError(
            f"API 오류: {code}, {message}"
        )

    return extract_traffic(root)


def main() -> None:
    """⑤ 성남시 대상 링크를 하나씩 순서대로 수집한다."""

    service_key = load_service_key()
    link_ids = load_target_link_ids()

    total = len(link_ids)
    start_time = time.perf_counter()

    records = []
    no_data = []
    failed = []

    print(f"성남시 수집 대상: {total}개\n")

    with requests.Session() as session:

        # ⑥ 동기 수집
        # 한 요청이 끝난 뒤 다음 linkId를 요청한다.
        for index, link_id in enumerate(
            link_ids,
            start=1,
        ):
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
                result = f"수집 실패: {error}"

            print(
                f"[{index}/{total}] "
                f"{link_id} {result}"
            )

            # API에 요청이 과도하게 몰리는 것을 방지
            time.sleep(0.1)

    # ⑦ 성남시 수집 결과를 Parquet으로 저장
    output_path = save_records(
        records,
        "sync",
        "seongnam",
    )

    elapsed = (
        time.perf_counter()
        - start_time
    )

    print("\n" + "=" * 50)
    print(f"저장 완료: {output_path}")
    print(f"전체 대상: {total}건")
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