import asyncio
import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

import aiohttp
import pandas as pd
from dotenv import load_dotenv


# ① 수집 대상 도로
ROUTE_ID = "1020000651"
ROUTE_NAME = "분당수서로"

# ② 경기도 교통정보 API 주소
LINK_LIST_URL = (
    "https://openapigits.gg.go.kr/api/rest/getRoadLinkInfoList"
)
TRAFFIC_URL = (
    "https://openapigits.gg.go.kr/api/rest/getRoadLinkTrafficInfo"
)

# ③ 비동기 요청 설정
CONCURRENCY_LIMIT = 5  # 동시에 최대 5개 요청
MAX_ATTEMPTS = 4       # 최초 요청 포함 최대 4번 시도

# ④ CSV에 저장할 열 이름과 XML 태그
FIELDS = {
    "collDate": "colldate",
    "routeId": "routeid",
    "routeNm": "routenm",
    "linkId": "linkid",
    "startNodeId": "startnodeid",
    "startNodeNm": "startnodenm",
    "endNodeId": "endnodeid",
    "endNodeNm": "endnodenm",
    "spd": "spd",
    "vol": "vol",
    "trvlTime": "trvltime",
    "linkDelayTime": "linkdelaytime",
    "congGrade": "conggrade",
}

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "data" / "raw"


def parse_xml(content: bytes) -> ET.Element:
    """⑤ XML 응답을 읽고 태그를 소문자로 통일한다."""
    root = ET.fromstring(content)

    for element in root.iter():
        if isinstance(element.tag, str):
            element.tag = element.tag.split("}")[-1].lower()

    return root


def get_status(root: ET.Element) -> tuple[str, str]:
    """⑥ API 처리 결과 코드와 메시지를 가져온다."""
    code = (root.findtext(".//headercd") or "").strip()
    message = (root.findtext(".//headermsg") or "").strip()

    return code, message


async def request_xml(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    url: str,
    params: dict[str, str],
    request_name: str,
) -> ET.Element:
    """⑦ API 요청 실패 시 일정 시간 후 다시 시도한다."""
    last_error = ""

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            # 동시에 실행되는 요청 수를 5개로 제한
            async with semaphore:
                async with session.get(url, params=params) as response:
                    content = await response.read()
                    response.raise_for_status()

            root = parse_xml(content)
            code, message = get_status(root)

            # 응답 코드가 비어 있거나 일시적 오류이면 재시도
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

            # 0.5초 → 1초 → 2초 순서로 대기
            delay = 0.5 * (2 ** (attempt - 1))

            print(
                f"{request_name} 재시도 "
                f"{attempt}/{MAX_ATTEMPTS - 1}: "
                f"{last_error} ({delay:.1f}초 후)"
            )

            await asyncio.sleep(delay)

    raise RuntimeError(
        f"{request_name} 요청 최종 실패: {last_error}"
    )


async def get_link_ids(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    service_key: str,
) -> list[str]:
    """⑧ 분당수서로를 구성하는 121개 linkId를 조회한다."""
    root = await request_xml(
        session,
        semaphore,
        LINK_LIST_URL,
        {
            "serviceKey": service_key,
            "routeId": ROUTE_ID,
        },
        "구간 목록",
    )

    code, message = get_status(root)

    if code != "0":
        raise RuntimeError(
            f"구간 목록 조회 실패: {code}, {message}"
        )

    link_ids = [
        (item.findtext("linkid") or "").strip()
        for item in root.findall(".//itemlist")
    ]

    # 빈 값과 중복 값 제거
    return list(dict.fromkeys(
        link_id for link_id in link_ids if link_id
    ))


async def get_traffic(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    service_key: str,
    link_id: str,
    index: int,
    total: int,
) -> tuple[str, dict[str, str] | None]:
    """⑨ linkId 한 개의 실시간 교통정보를 조회한다."""
    try:
        root = await request_xml(
            session,
            semaphore,
            TRAFFIC_URL,
            {
                "serviceKey": service_key,
                "linkId": link_id,
            },
            link_id,
        )

        code, message = get_status(root)

        # headerCd=4는 현재 데이터가 없는 구간
        if code == "4":
            print(
                f"[{index}/{total}] "
                f"{link_id} 데이터 없음"
            )
            return "no_data", None

        if code != "0":
            print(
                f"[{index}/{total}] "
                f"{link_id} API 오류: {code}, {message}"
            )
            return "failed", None

        item = root.find(".//itemlist")

        if item is None:
            return "no_data", None

        # XML 데이터를 CSV 한 행으로 변환
        record = {
            column: (item.findtext(tag) or "").strip()
            for column, tag in FIELDS.items()
        }

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
    """⑩ 121개 구간을 비동기로 수집하고 CSV로 저장한다."""
    load_dotenv(BASE_DIR / ".env")

    service_key = unquote(
        os.getenv("SERVICE_KEY", "").strip()
    )

    if not service_key:
        raise ValueError(
            ".env 파일에 SERVICE_KEY가 없습니다."
        )

    started_at = time.perf_counter()

    timeout = aiohttp.ClientTimeout(total=30)
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    connector = aiohttp.TCPConnector(
        limit_per_host=CONCURRENCY_LIMIT
    )

    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
    ) as session:
        link_ids = await get_link_ids(
            session,
            semaphore,
            service_key,
        )

        total = len(link_ids)

        print(f"{ROUTE_NAME} 구간 수: {total}개")
        print(f"동시 요청 제한: {CONCURRENCY_LIMIT}개")
        print(f"최대 요청 횟수: {MAX_ATTEMPTS}회\n")

        # ⑪ 121개의 요청 작업을 한꺼번에 등록
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

        results = await asyncio.gather(*tasks)

    records = []
    no_data_ids = []
    failed_ids = []

    # ⑫ 수집 결과를 성공·데이터 없음·실패로 분류
    for link_id, (status, record) in zip(
        link_ids,
        results,
    ):
        if status == "success" and record:
            records.append(record)
        elif status == "no_data":
            no_data_ids.append(link_id)
        else:
            failed_ids.append(link_id)

    # ⑬ 수집 결과를 CSV로 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = (
        OUTPUT_DIR
        / f"bundang_suseo_async_{timestamp}.csv"
    )

    pd.DataFrame(
        records,
        columns=FIELDS.keys(),
    ).to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    elapsed = time.perf_counter() - started_at

    print("\n" + "=" * 50)
    print(f"CSV 저장 완료: {output_path}")
    print(f"전체 구간: {len(link_ids)}건")
    print(f"수집 성공: {len(records)}건")
    print(f"데이터 없음: {len(no_data_ids)}건")
    print(f"요청 실패: {len(failed_ids)}건")
    print(f"전체 실행시간: {elapsed:.2f}초")

    if failed_ids:
        print(
            "실패한 linkId: "
            + ", ".join(failed_ids)
        )


if __name__ == "__main__":
    # ⑭ 비동기 프로그램 시작
    asyncio.run(main())