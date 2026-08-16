# Gyeonggi Traffic Data Pipeline

경기도 주요 도로 실시간 소통정보 Open API를 활용하여  
성남시 주요 도로의 교통 데이터를 동기·비동기·배치 방식으로 수집하고,  
도로 공간정보와 결합하여 GeoJSON으로 변환하는 프로젝트

## 프로젝트 개요

### 프로젝트 목적

동일한 성남시 교통 데이터를 서로 다른 방식으로 수집하여  
동기, 비동기, 배치 처리 방식의 특징과 실행시간을 비교한다.

또한 실시간 교통정보와 도로 Geometry를 `linkId` 기준으로 결합하여  
지도에서 활용할 수 있는 GeoJSON 공간데이터를 생성한다.

### 수집 대상

- 지역: 성남시 수정구·중원구·분당구
- 경기도 교통 API 주요도로: 152개
- 경기도 교통 API 전체 linkId: 27,895개
- 성남시 공간데이터 linkId: 10,653개
- 최종 수집 대상: 508개 linkId
- 수집 대상 도로명: 21개
- API 응답 형식: XML
- Raw 저장 형식: Parquet
- 공간데이터 결과 형식: GeoJSON

## 프로젝트 구조

```text
gyeonggi-traffic-data-pipeline/
├─ traffic/
│  ├─ __init__.py
│  └─ common.py
├─ data/
│  ├─ raw/
│  │  ├─ seongnam_sync_*.parquet
│  │  ├─ seongnam_async_*.parquet
│  │  └─ seongnam_batch_*.parquet
│  ├─ reference/
│  │  └─ seongnam_target_links.parquet
│  ├─ processed/
│  │  ├─ seongnam_sync.geojson
│  │  ├─ seongnam_async.geojson
│  │  └─ seongnam_batch.geojson
│  └─ spatial/
│     └─ 공간정보 원본 데이터
├─ sync_collect.py
├─ async_collect.py
├─ batch_collect.py
├─ prepare_reference.py
├─ geojson_convert.py
├─ results_summary.md
├─ README.md
├─ .gitignore
└─ .env
```

## 수집 데이터

- 수집 시각
- 도로 ID / 도로명
- 구간 ID
- 시작 지점 / 종료 지점
- 속도
- 교통량
- 통행시간
- 지체시간
- 혼잡등급

## 공간데이터

교통 API에는 도로의 좌표 및 선형 정보가 포함되어 있지 않기 때문에 국가교통정보센터의 표준노드링크 데이터를 사용하였다.
`MOCT_LINK`의 `LINK_ID`와 교통정보의 `linkId`를 연결하여 각 도로 구간의 LineString Geometry를 확보하였다.
또한 시군구 경계 데이터를 이용하여 성남시 수정구·중원구·분당구 영역에 포함되는 도로를 판별하였다.

## 실행 환경

- Python 3.11
- uv
- requests
- aiohttp
- pandas
- python-dotenv
- pyarrow
- geopandas

## 실행 방법

### 1. 성남시 수집 대상 생성

```powershell
python prepare_reference.py
```

### 2. 동기 수집

```powershell
python sync_collect.py
```

### 3. 비동기 수집

```powershell
python async_collect.py
```

### 4. 배치 수집

```powershell
python batch_collect.py
```

### 5. GeoJSON 생성

```powershell
python geojson_convert.py
```

## 수집 방식 비교

- 동기
  - 전체 대상: 508건
  - 수집 성공: 482건
  - 데이터 없음: 22건
  - 요청 실패: 4건
  - 실행시간: 66.08초

- 비동기
  - 전체 대상: 508건
  - 수집 성공: 482건
  - 데이터 없음: 26건
  - 요청 실패: 0건
  - 실행시간: 5.32초

- 배치
  - 전체 대상: 508건
  - 전체 배치: 26개
  - 수집 성공: 482건
  - 데이터 없음: 26건
  - 요청 실패: 0건
  - 실행시간: 37.54초

비동기 방식은 동기 방식보다 약 12.4배 빠르게 처리되었다.

배치 방식은 전체 데이터를 일정한 크기로 나누고  
배치 사이에 대기시간을 두어 API 서버에 요청이 집중되는 것을 줄이도록 구성하였다.

## GeoJSON 변환 결과

- 동기: 482건 연결 / 누락 0건
- 비동기: 482건 연결 / 누락 0건
- 배치: 482건 연결 / 누락 0건
- 최종 좌표계: EPSG:4326

세 방식 모두 수집된 교통정보와 Geometry가 100% 연결되었다.

## 데이터 처리 흐름

```text
경기도 교통정보 Open API
        ↓
경기도 주요도로 및 linkId 조회
        ↓
성남시 행정구역 경계 + 표준노드링크
        ↓
성남시 수집 대상 508개 linkId 생성
        ↓
동기 / 비동기 / 배치 방식으로 실시간 교통정보 수집
        ↓
XML 응답 파싱
        ↓
Parquet 저장
        ↓
linkId + 도로 Geometry 결합
        ↓
GeoJSON 저장
```