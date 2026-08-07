import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import requests
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

# ③ CSV에 저장할 열 이름과 XML 태그
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


def get_xml(
    session: requests.Session,
    url: str,
    params: dict[str, str],
) -> ET.Element:
    """④ API를 호출하고 XML 응답을 읽는다."""
    response = session.get(url, params=params, timeout=20)
    response.raise_for_status()

    root = ET.fromstring(response.content)

    # API마다 태그의 대소문자가 다를 수 있어 소문자로 통일
    for element in root.iter():
        if isinstance(element.tag, str):
            element.tag = element.tag.split("}")[-1].lower()

    return root


def get_status(root: ET.Element) -> tuple[str, str]:
    """⑤ API 처리 결과 코드와 메시지를 가져온다."""
    code = (root.findtext(".//headercd") or "").strip()
    message = (root.findtext(".//headermsg") or "").strip()

    return code, message


def get_link_ids(
    session: requests.Session,
    service_key: str,
) -> list[str]:
    """⑥ 분당수서로를 구성하는 121개 linkId를 조회한다."""
    root = get_xml(
        session,
        LINK_LIST_URL,
        {
            "serviceKey": service_key,
            "routeId": ROUTE_ID,
        },
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


def get_traffic(
    session: requests.Session,
    service_key: str,
    link_id: str,
) -> dict[str, str] | None:
    """⑦ linkId 한 개의 실시간 교통정보를 조회한다."""
    root = get_xml(
        session,
        TRAFFIC_URL,
        {
            "serviceKey": service_key,
            "linkId": link_id,
        },
    )

    code, message = get_status(root)

    # headerCd=4는 해당 구간에 현재 데이터가 없다는 뜻
    if code == "4":
        return None

    if code != "0":
        raise RuntimeError(
            f"API 오류: {code}, {message}"
        )

    item = root.find(".//itemlist")

    if item is None:
        return None

    # XML 데이터를 CSV 한 행으로 변환
    return {
        column: (item.findtext(tag) or "").strip()
        for column, tag in FIELDS.items()
    }


def main() -> None:
    """⑧ 121개 구간을 순서대로 수집하고 CSV로 저장한다."""
    load_dotenv(BASE_DIR / ".env")

    service_key = unquote(
        os.getenv("SERVICE_KEY", "").strip()
    )

    if not service_key:
        raise ValueError(
            ".env 파일에 SERVICE_KEY가 없습니다."
        )

    started_at = time.perf_counter()

    records = []
    no_data_ids = []
    failed_ids = []

    with requests.Session() as session:
        link_ids = get_link_ids(session, service_key)
        total = len(link_ids)

        print(f"{ROUTE_NAME} 구간 수: {total}개\n")

        # ⑨ 동기 방식: 한 요청이 끝난 뒤 다음 요청 실행
        for index, link_id in enumerate(link_ids, start=1):
            try:
                traffic = get_traffic(
                    session,
                    service_key,
                    link_id,
                )

                if traffic is None:
                    no_data_ids.append(link_id)
                    result = "데이터 없음"
                else:
                    records.append(traffic)
                    result = "수집 성공"

            except (
                requests.RequestException,
                RuntimeError,
            ) as error:
                failed_ids.append(link_id)
                result = f"수집 실패: {error}"

            print(
                f"[{index}/{total}] "
                f"{link_id} {result}"
            )

            # API 서버에 요청이 너무 몰리지 않도록 잠시 대기
            time.sleep(0.1)

    # ⑩ 수집 결과를 CSV로 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = (
        OUTPUT_DIR
        / f"bundang_suseo_sync_{timestamp}.csv"
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


if __name__ == "__main__":
    main()