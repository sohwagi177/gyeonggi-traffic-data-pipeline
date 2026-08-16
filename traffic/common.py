import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
from dotenv import load_dotenv


# ① 현재 테스트 대상
# 기존 코드가 계속 작동하도록 일단 유지한다.
ROUTE_ID = "1020000651"
ROUTE_NAME = "분당수서로"
DATA_NAME = "bundang_suseo"


# ② 경기도 교통정보 API
# 전체 주요도로 목록
ROUTE_LIST_URL = (
    "https://openapigits.gg.go.kr/api/rest/getRoadInfoList"
)

# 특정 도로의 linkId 목록
LINK_LIST_URL = (
    "https://openapigits.gg.go.kr/api/rest/getRoadLinkInfoList"
)

# 특정 도로의 전체 교통정보
ROUTE_TRAFFIC_URL = (
    "https://openapigits.gg.go.kr/api/rest/getRoadLinkTrafficInfoList"
)

# 특정 linkId 하나의 교통정보
TRAFFIC_URL = (
    "https://openapigits.gg.go.kr/api/rest/getRoadLinkTrafficInfo"
)


# ③ 저장할 데이터 항목
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


# ④ 프로젝트 경로
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "raw"


def load_service_key() -> str:
    """⑤ .env에서 API Key를 불러온다."""
    load_dotenv(BASE_DIR / ".env")

    service_key = unquote(
        os.getenv("SERVICE_KEY", "").strip()
    )

    if not service_key:
        raise ValueError(
            ".env 파일에 SERVICE_KEY가 없습니다."
        )

    return service_key


def parse_xml(content: bytes) -> ET.Element:
    """⑥ XML 태그를 소문자로 통일한다."""
    root = ET.fromstring(content)

    for element in root.iter():
        if isinstance(element.tag, str):
            element.tag = element.tag.split("}")[-1].lower()

    return root


def get_status(root: ET.Element) -> tuple[str, str]:
    """⑦ API 응답 코드와 메시지를 가져온다."""
    return (
        (root.findtext(".//headercd") or "").strip(),
        (root.findtext(".//headermsg") or "").strip(),
    )


def extract_routes(
    root: ET.Element,
) -> list[dict[str, str]]:
    """⑧ 전체 도로 목록에서 routeId와 도로명을 추출한다."""
    routes = []

    for item in root.findall(".//itemlist"):
        route_id = (
            item.findtext("routeid") or ""
        ).strip()

        route_name = (
            item.findtext("routenm") or ""
        ).strip()

        if route_id:
            routes.append(
                {
                    "routeId": route_id,
                    "routeNm": route_name,
                }
            )

    # 같은 routeId가 중복된 경우 제거
    unique_routes = {}

    for route in routes:
        unique_routes[route["routeId"]] = route

    return list(unique_routes.values())


def extract_link_ids(
    root: ET.Element,
) -> list[str]:
    """⑨ XML에서 linkId 목록을 추출한다."""
    link_ids = [
        (item.findtext("linkid") or "").strip()
        for item in root.findall(".//itemlist")
    ]

    return list(
        dict.fromkeys(
            link_id
            for link_id in link_ids
            if link_id
        )
    )


def extract_traffic(
    root: ET.Element,
) -> dict[str, str] | None:
    """⑩ XML에서 교통정보 한 건을 추출한다."""
    item = root.find(".//itemlist")

    if item is None:
        return None

    return {
        column: (item.findtext(tag) or "").strip()
        for column, tag in FIELDS.items()
    }


def extract_traffic_list(
    root: ET.Element,
) -> list[dict[str, str]]:
    """⑪ XML에서 여러 구간의 교통정보를 추출한다."""
    records = []

    for item in root.findall(".//itemlist"):
        record = {
            column: (
                item.findtext(tag) or ""
            ).strip()
            for column, tag in FIELDS.items()
        }

        records.append(record)

    return records


def save_records(
    records: list[dict[str, str]],
    method: str,
    data_name: str = DATA_NAME,
) -> Path:
    """⑫ 수집 결과를 Parquet 파일로 저장한다."""
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = time.strftime("%Y%m%d_%H%M%S")

    output_path = (
        OUTPUT_DIR
        / f"{data_name}_{method}_{timestamp}.parquet"
    )

    pd.DataFrame(
        records,
        columns=FIELDS.keys(),
    ).to_parquet(
        output_path,
        index=False,
        engine="pyarrow",
    )

    return output_path