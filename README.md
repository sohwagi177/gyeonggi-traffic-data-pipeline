# Gyeonggi Traffic Data Pipeline

경기도 주요 도로 실시간 소통정보 Open API를 활용하여  
분당수서로의 교통 데이터를 동기·비동기·배치 방식으로 수집하고 비교하는 프로젝트

## 프로젝트 개요

### 프로젝트 목적

동일한 교통 데이터를 서로 다른 방식으로 수집하여  
동기, 비동기, 배치 처리 방식의 특징과 실행시간을 비교한다.

### 수집 대상

- 도로: 분당수서로
- routeId: `1020000651`
- 전체 구간: 121개 linkId
- 데이터 형식: XML
- 저장 형식: CSV

### 프로젝트 구조

```text
gyeonggi-traffic-data-pipeline/
├─ data/
│  └─ raw/
├─ sync_collect.py
├─ async_collect.py
├─ batch_collect.py
├─ results_summary.md
├─ README.md
└─ .env
수집 데이터
수집 시각
도로 ID / 도로명
구간 ID
시작 지점 / 종료 지점
속도
교통량
통행시간
지체시간
혼잡등급
실행 환경
Python 3.11
uv
requests
aiohttp
pandas
python-dotenv
실행 방법

동기 수집

python sync_collect.py

비동기 수집

python async_collect.py

배치 수집

python batch_collect.py
수집 방식 비교
동기: 121개 구간 순차 요청 / 15.28초
비동기: 최대 5개 동시 요청 / 1.20초
배치: 20개씩 총 7개 배치 처리 / 9.13초
배치 사이 대기시간: 1초

비동기 방식은 동기 방식보다 약 12.7배 빠르게 처리되었다.

배치 방식은 전체 데이터를 일정한 크기로 나누고
배치 사이에 대기시간을 두어 서버 부하를 조절하도록 구성하였다.

데이터 수집 흐름
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