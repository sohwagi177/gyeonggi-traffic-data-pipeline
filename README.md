# Gyeonggi Traffic Data Pipeline

경기도 주요 도로 실시간 소통정보 Open API를 활용하여  
분당수서로의 교통 데이터를 동기·비동기·배치 방식으로 수집하고 비교하는 프로젝트

## 프로젝트 개요

### 프로젝트 목적
- Open API 기반 데이터 수집 과정 이해
- 동기·비동기 수집 방식 구현 및 실행시간 비교
- 배치 방식으로 시간대별 교통정보 반복 수집
- 수집 데이터를 CSV로 저장하여 향후 DB 구축에 활용

### 수집 대상
- 도로명: 분당수서로
- `routeId`: `1020000651`
- 전체 구간: 121개 `linkId`

### 프로젝트 구조

```text
gyeonggi-traffic-data-pipeline/
├─ data/
│  └─ raw/                 # 수집된 CSV 파일
├─ .env                    # API Key
├─ .gitignore
├─ sync_collect.py         # 동기 수집
├─ async_collect.py        # 비동기 수집
├─ batch_collect.py        # 배치 수집
├─ results_summary.md      # 수집 방식 비교 결과
└─ README.md
```

### 수집 데이터

| 항목 | 설명 |
| `collDate` | 데이터 수집 시각 |
| `routeId` | 도로 ID |
| `routeNm` | 도로명 |
| `linkId` | 도로 구간 ID |
| `startNodeId` | 시작 노드 ID |
| `startNodeNm` | 시작 지점명 |
| `endNodeId` | 종료 노드 ID |
| `endNodeNm` | 종료 지점명 |
| `spd` | 속도 |
| `vol` | 교통량 |
| `trvlTime` | 통행시간 |
| `linkDelayTime` | 지체시간 |
| `congGrade` | 혼잡등급 |

### 실행 환경

- Python 3.11
- uv
- requests
- aiohttp
- pandas
- python-dotenv

```bash
uv pip install requests aiohttp pandas python-dotenv
```
### 실행 방법

동기 수집:

```bash
python sync_collect.py
```

비동기 수집:

```bash
python async_collect.py
```

배치 수집:

```bash
python batch_collect.py
```

### 수집 방식 비교

| 동기 | 121개 구간 순차 요청 | 15.28초 |
| 비동기 | 최대 5개 동시 요청 | 1.20초 |
| 배치 | 60초 간격으로 3회 반복 | 3회 모두 성공 |

비동기 방식은 테스트에서 동기 방식보다 약 12.7배 빠르게 수집되었다.

실시간 API 특성상 실행 시점에 따라 데이터가 제공되지 않는 구간 수는 달라질 수 있다.

### 데이터 수집 흐름

```text
경기도 교통정보 Open API
        ↓
분당수서로 routeId
        ↓
121개 linkId 조회
        ↓
각 구간 실시간 교통정보 요청
        ↓
XML 응답 파싱
        ↓
CSV 저장
```