import asyncio
import time
import xml.etree.ElementTree as ET

import aiohttp

from traffic import (
    TRAFFIC_URL,
    load_service_key,
    parse_xml,
    get_status,
    extract_traffic,
    save_records,
)

# ① 성남시 508개 LINK_ID 불러오는 함수 재사용
from sync_collect import load_target_link_ids


# ② 비동기 요청 설정
CONCURRENCY_LIMIT = 5
MAX_ATTEMPTS = 4


async def request_xml(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    service_key: str,
    link_id: str,
):
    """③ 비동기로 API를 호출하고 일시적인 오류는 재시도한다."""

    last_error = ""

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            async with semaphore:
                async with session.get(
                    TRAFFIC_URL,
                    params={
                        "serviceKey": service_key,
                        "linkId": link_id,
                    },
                ) as response:
                    content = await response.read()
                    response.raise_for_status()

            root = parse_xml(content)
            code, message = get_status(root)

            # 일시적인 비정상 응답이면 재시도
            if code in {"", "1", "8", "99"}:
                raise RuntimeError(
                    f"headerCd={code or '빈 값'}, "
                    f"message={message or '없음'}"
                )

            return root

        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            ET.ParseError,
            RuntimeError,
        ) as error:
            last_error = str(error)

            if attempt == MAX_ATTEMPTS:
                break

            delay = 0.5 * (2 ** (attempt - 1))

            print(
                f"{link_id} 재시도 "
                f"{attempt}/{MAX_ATTEMPTS - 1}: "
                f"{last_error} "
                f"({delay:.1f}초 후)"
            )

            await asyncio.sleep(delay)

    raise RuntimeError(
        f"{link_id} 요청 최종 실패: {last_error}"
    )


async def get_traffic(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    service_key: str,
    link_id: str,
    index: int,
    total: int,
):
    """④ linkId 한 개의 최신 교통정보를 조회한다."""

    try:
        root = await request_xml(
            session,
            semaphore,
            service_key,
            link_id,
        )

        code, message = get_status(root)

        if code == "4":
            print(
                f"[{index}/{total}] "
                f"{link_id} 데이터 없음"
            )
            return "no_data", None

        if code != "0":
            print(
                f"[{index}/{total}] "
                f"{link_id} API 오류: "
                f"{code}, {message}"
            )
            return "failed", None

        record = extract_traffic(root)

        if record is None:
            print(
                f"[{index}/{total}] "
                f"{link_id} 데이터 없음"
            )
            return "no_data", None

        print(
            f"[{index}/{total}] "
            f"{link_id} 수집 성공"
        )

        return "success", record

    except RuntimeError as error:
        print(
            f"[{index}/{total}] "
            f"{link_id} 수집 실패: {error}"
        )

        return "failed", None


async def main() -> None:
    """⑤ 성남시 대상 링크를 비동기 방식으로 수집한다."""

    # API Key는 시작할 때 한 번만 불러온다.
    service_key = load_service_key()

    # 성남시 508개 LINK_ID
    link_ids = load_target_link_ids()
    total = len(link_ids)

    start_time = time.perf_counter()

    print(f"성남시 수집 대상: {total}개")
    print(f"동시 요청 제한: {CONCURRENCY_LIMIT}개")
    print(f"최대 요청 횟수: {MAX_ATTEMPTS}회\n")

    semaphore = asyncio.Semaphore(
        CONCURRENCY_LIMIT
    )

    timeout = aiohttp.ClientTimeout(
        total=30
    )

    connector = aiohttp.TCPConnector(
        limit_per_host=CONCURRENCY_LIMIT
    )

    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
    ) as session:

        # ⑥ 508개 요청을 등록하고 비동기로 처리
        tasks = [
            get_traffic(
                session,
                semaphore,
                service_key,
                link_id,
                index,
                total,
            )
            for index, link_id in enumerate(
                link_ids,
                start=1,
            )
        ]

        results = await asyncio.gather(
            *tasks
        )

    records = []
    no_data = []
    failed = []

    # ⑦ 결과 분류
    for link_id, (status, record) in zip(
        link_ids,
        results,
    ):
        if status == "success" and record:
            records.append(record)

        elif status == "no_data":
            no_data.append(link_id)

        else:
            failed.append(link_id)

    # ⑧ Parquet 저장
    output_path = save_records(
        records,
        "async",
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
    # ⑨ 비동기 프로그램 시작
    asyncio.run(main())