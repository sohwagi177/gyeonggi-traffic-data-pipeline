import time
from pathlib import Path

import geopandas as gpd
import pandas as pd


# ① 프로젝트 경로
BASE_DIR = Path(__file__).resolve().parent

RAW_DIR = BASE_DIR / "data" / "raw"
SPATIAL_DIR = BASE_DIR / "data" / "spatial"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

LINK_PATH = (
    SPATIAL_DIR
    / "MOCT_LINK.shp"
)


def get_latest_file(method: str) -> Path:
    """② 수집 방식별 가장 최근 Parquet 파일을 찾는다."""

    files = list(
        RAW_DIR.glob(
            f"seongnam_{method}_*.parquet"
        )
    )

    if not files:
        raise FileNotFoundError(
            f"{method} Parquet 파일이 없습니다."
        )

    return max(
        files,
        key=lambda path: path.stat().st_mtime,
    )


def load_geometry(
    target_link_ids: set[str],
) -> gpd.GeoDataFrame:
    """③ 필요한 LINK_ID의 Geometry만 불러온다."""

    print("도로 Geometry 읽는 중...")

    roads = gpd.read_file(
        LINK_PATH,
        columns=[
            "LINK_ID",
            "ROAD_NAME",
            "ROAD_NO",
            "MAX_SPD",
            "LENGTH",
            "geometry",
        ],
    )

    roads["LINK_ID"] = (
        roads["LINK_ID"]
        .astype(str)
        .str.strip()
    )

    roads = roads[
        roads["LINK_ID"].isin(
            target_link_ids
        )
    ].copy()

    roads = roads.drop_duplicates(
        subset="LINK_ID"
    )

    return roads


def convert_geojson(
    traffic_path: Path,
    roads: gpd.GeoDataFrame,
    method: str,
) -> dict:
    """④ Parquet 교통정보와 Geometry를 결합해 GeoJSON으로 변환한다."""

    start_time = time.perf_counter()

    # 교통정보 읽기
    traffic = pd.read_parquet(
        traffic_path
    )

    traffic["linkId"] = (
        traffic["linkId"]
        .astype(str)
        .str.strip()
    )

    # 교통정보 + Geometry 결합
    merged = roads.merge(
        traffic,
        left_on="LINK_ID",
        right_on="linkId",
        how="right",
    )

    merged = gpd.GeoDataFrame(
        merged,
        geometry="geometry",
        crs=roads.crs,
    )

    matched = int(
        merged.geometry.notna().sum()
    )

    missing = int(
        merged.geometry.isna().sum()
    )

    # Geometry가 있는 데이터만 저장
    merged = merged[
        merged.geometry.notna()
    ].copy()

    # GeoJSON용 위도·경도 좌표계
    merged = merged.to_crs(
        epsg=4326
    )

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        PROCESSED_DIR
        / f"seongnam_{method}.geojson"
    )

    merged.to_file(
        output_path,
        driver="GeoJSON",
        index=False,
    )

    elapsed = (
        time.perf_counter()
        - start_time
    )

    return {
        "method": method,
        "input": len(traffic),
        "matched": matched,
        "missing": missing,
        "output": len(merged),
        "time": elapsed,
        "path": output_path,
    }


def main() -> None:
    """⑤ 동기·비동기·배치 결과의 GeoJSON 변환을 비교한다."""

    methods = [
        "sync",
        "async",
        "batch",
    ]

    # ⑥ 각 방식의 최신 Parquet 찾기
    traffic_files = {
        method: get_latest_file(method)
        for method in methods
    }

    print("===== 비교 대상 =====")

    for method, path in traffic_files.items():
        print(
            f"{method:5} → {path.name}"
        )

    # ⑦ 세 파일에서 필요한 모든 linkId 확보
    all_link_ids = set()

    for path in traffic_files.values():
        df = pd.read_parquet(
            path,
            columns=["linkId"],
        )

        ids = (
            df["linkId"]
            .astype(str)
            .str.strip()
        )

        all_link_ids.update(ids)

    # Geometry는 한 번만 읽는다.
    roads = load_geometry(
        all_link_ids
    )

    print(
        f"Geometry 준비: "
        f"{len(roads):,}개\n"
    )

    # ⑧ 세 방식 변환
    results = []

    for method in methods:
        print(
            f"===== {method} 변환 시작 ====="
        )

        result = convert_geojson(
            traffic_files[method],
            roads,
            method,
        )

        results.append(result)

        print(
            f"입력: {result['input']}건"
        )
        print(
            f"Geometry 연결: "
            f"{result['matched']}건"
        )
        print(
            f"Geometry 없음: "
            f"{result['missing']}건"
        )
        print(
            f"GeoJSON 저장: "
            f"{result['output']}건"
        )
        print(
            f"변환시간: "
            f"{result['time']:.4f}초\n"
        )

    # ⑨ 최종 비교
    print("=" * 60)
    print("GeoJSON 변환 비교 결과")
    print("=" * 60)

    for result in results:
        print(
            f"{result['method']:5} | "
            f"입력 {result['input']:3}건 | "
            f"출력 {result['output']:3}건 | "
            f"누락 {result['missing']:2}건 | "
            f"{result['time']:.4f}초"
        )

    print("\n===== 저장 파일 =====")

    for result in results:
        print(
            f"{result['method']:5} → "
            f"{result['path']}"
        )


if __name__ == "__main__":
    main()