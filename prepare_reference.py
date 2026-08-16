from pathlib import Path

import geopandas as gpd
import requests

from traffic import (
    ROUTE_LIST_URL,
    LINK_LIST_URL,
    load_service_key,
    parse_xml,
    get_status,
    extract_routes,
    extract_link_ids,
)


# ① 프로젝트 경로
BASE_DIR = Path(__file__).resolve().parent

LINK_PATH = (
    BASE_DIR
    / "data"
    / "spatial"
    / "MOCT_LINK.shp"
)

BOUNDARY_PATH = (
    BASE_DIR
    / "data"
    / "spatial"
    / "bnd_sigungu_00_2025_2Q.shp"
)

REFERENCE_DIR = (
    BASE_DIR
    / "data"
    / "reference"
)

OUTPUT_PATH = (
    REFERENCE_DIR
    / "seongnam_target_links.parquet"
)


def get_all_api_link_ids() -> tuple[set[str], list[str]]:
    """② 경기도 교통 API의 전체 주요도로 linkId를 가져온다."""

    service_key = load_service_key()
    all_link_ids = set()
    failed_routes = []

    with requests.Session() as session:

        # 경기도 주요도로 목록 조회
        response = session.get(
            ROUTE_LIST_URL,
            params={
                "serviceKey": service_key,
            },
            timeout=30,
        )
        response.raise_for_status()

        root = parse_xml(response.content)
        code, message = get_status(root)

        if code != "0":
            raise RuntimeError(
                f"도로 목록 조회 실패: {code}, {message}"
            )

        routes = extract_routes(root)
        total = len(routes)

        print(f"경기도 주요도로: {total}개\n")

        # ③ 각 주요도로의 linkId 조회
        for index, route in enumerate(
            routes,
            start=1,
        ):
            route_id = route["routeId"]
            route_name = route["routeNm"]

            try:
                response = session.get(
                    LINK_LIST_URL,
                    params={
                        "serviceKey": service_key,
                        "routeId": route_id,
                    },
                    timeout=30,
                )
                response.raise_for_status()

                root = parse_xml(response.content)
                code, message = get_status(root)

                if code == "0":
                    link_ids = extract_link_ids(root)
                    all_link_ids.update(link_ids)

                elif code != "4":
                    failed_routes.append(route_id)

                    print(
                        f"[{index}/{total}] "
                        f"{route_name} 조회 실패: "
                        f"{code}, {message}"
                    )

            except requests.RequestException as error:
                failed_routes.append(route_id)

                print(
                    f"[{index}/{total}] "
                    f"{route_name} 요청 실패: {error}"
                )

            # 10개 도로마다 진행 상황 출력
            if index % 10 == 0 or index == total:
                print(
                    f"[{index}/{total}] "
                    f"현재 linkId "
                    f"{len(all_link_ids):,}개"
                )

    return all_link_ids, failed_routes


def get_seongnam_roads():
    """④ 공간데이터에서 성남시 도로를 추출한다."""

    print("\n시군구 경계 읽는 중...")

    boundary = gpd.read_file(BOUNDARY_PATH)

    # 수정구 + 중원구 + 분당구
    seongnam = boundary[
        boundary["SIGUNGU_NM"].str.startswith(
            "성남시",
            na=False,
        )
    ].copy()

    if seongnam.empty:
        raise RuntimeError(
            "성남시 행정구역을 찾지 못했습니다."
        )

    # 도로 좌표계 확인
    road_sample = gpd.read_file(
        LINK_PATH,
        rows=1,
    )

    # 행정구역 좌표계를 도로 좌표계와 통일
    seongnam = seongnam.to_crs(
        road_sample.crs
    )

    # 성남시 3개 구를 하나의 영역으로 합침
    seongnam_area = (
        seongnam.geometry.union_all()
    )

    # 성남시 주변 도로만 먼저 읽기
    bbox = tuple(seongnam.total_bounds)

    print("성남시 주변 도로 읽는 중...")

    roads = gpd.read_file(
        LINK_PATH,
        bbox=bbox,
    )

    # 실제 성남시 경계와 겹치는 도로만 선택
    seongnam_roads = roads[
        roads.geometry.intersects(
            seongnam_area
        )
    ].copy()

    # LINK_ID 형식 통일
    seongnam_roads["LINK_ID"] = (
        seongnam_roads["LINK_ID"]
        .astype(str)
        .str.strip()
    )

    # 중복 제거
    seongnam_roads = (
        seongnam_roads
        .drop_duplicates(
            subset="LINK_ID"
        )
    )

    return seongnam_roads


def main() -> None:
    """⑤ 성남시 실시간 교통 수집 대상 링크를 생성한다."""

    if not LINK_PATH.exists():
        raise FileNotFoundError(
            f"도로 파일이 없습니다: {LINK_PATH}"
        )

    if not BOUNDARY_PATH.exists():
        raise FileNotFoundError(
            f"경계 파일이 없습니다: {BOUNDARY_PATH}"
        )

    # ⑥ 성남시 공간 링크 추출
    seongnam_roads = get_seongnam_roads()

    seongnam_link_ids = set(
        seongnam_roads["LINK_ID"]
    )

    print(
        f"\n성남시 공간 LINK_ID: "
        f"{len(seongnam_link_ids):,}개"
    )

    # ⑦ 경기도 교통 API 전체 링크 조회
    print(
        "\n경기도 교통 API "
        "전체 linkId 조회 중..."
    )

    api_link_ids, failed_routes = (
        get_all_api_link_ids()
    )

    # ⑧ 성남시 공간 링크와 API 링크의 교집합
    target_link_ids = (
        seongnam_link_ids
        & api_link_ids
    )

    spatial_only = (
        seongnam_link_ids
        - api_link_ids
    )

    # ⑨ 실제 수집 대상 도로 정보
    target_roads = seongnam_roads[
        seongnam_roads["LINK_ID"].isin(
            target_link_ids
        )
    ].copy()

    target_roads = target_roads.sort_values(
        "LINK_ID"
    )

    print("\n===== 최종 비교 결과 =====")
    print(
        f"경기도 API LINK_ID: "
        f"{len(api_link_ids):,}개"
    )
    print(
        f"성남시 공간 LINK_ID: "
        f"{len(seongnam_link_ids):,}개"
    )
    print(
        f"성남시 수집 대상 LINK_ID: "
        f"{len(target_roads):,}개"
    )
    print(
        f"성남시 공간에만 존재: "
        f"{len(spatial_only):,}개"
    )
    print(
        f"조회 실패 도로: "
        f"{len(failed_routes)}개"
    )

    # ⑩ 수집에 필요한 속성만 Parquet으로 저장
    REFERENCE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    target_table = target_roads[
        [
            "LINK_ID",
            "ROAD_NAME",
            "ROAD_NO",
            "MAX_SPD",
            "LENGTH",
        ]
    ].copy()

    target_table.to_parquet(
        OUTPUT_PATH,
        index=False,
        engine="pyarrow",
    )

    print("\n===== 저장 완료 =====")
    print(f"파일: {OUTPUT_PATH}")
    print(f"저장된 링크: {len(target_table):,}개")

    print("\n===== 저장 데이터 일부 =====")
    print(
        target_table
        .head(20)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()