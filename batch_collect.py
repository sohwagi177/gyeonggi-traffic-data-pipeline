import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path


# ① 배치 실행 설정
RUN_COUNT = 3          # 총 수집 횟수
INTERVAL_SECONDS = 60  # 수집 간격: 60초

# ② 프로젝트 경로와 실행할 비동기 수집 파일
BASE_DIR = Path(__file__).resolve().parent
COLLECTOR_FILE = BASE_DIR / "async_collect.py"


def run_collection(run_number: int) -> bool:
    """③ async_collect.py를 한 번 실행한다."""
    started_at = datetime.now()

    print("\n" + "=" * 60)
    print(f"{run_number}/{RUN_COUNT}회차 수집 시작")
    print(f"시작 시각: {started_at:%Y-%m-%d %H:%M:%S}")
    print("=" * 60)

    # 현재 가상환경의 Python으로 비동기 수집기 실행
    result = subprocess.run(
        [sys.executable, str(COLLECTOR_FILE)],
        cwd=BASE_DIR,
    )

    finished_at = datetime.now()

    if result.returncode == 0:
        print(f"{run_number}회차 수집 완료")
        print(f"종료 시각: {finished_at:%Y-%m-%d %H:%M:%S}")
        return True

    print(f"{run_number}회차 수집 실패")
    print(f"종료 코드: {result.returncode}")
    return False


def main() -> None:
    """④ 일정한 간격으로 비동기 수집기를 반복 실행한다."""
    if not COLLECTOR_FILE.exists():
        raise FileNotFoundError(
            "async_collect.py 파일을 찾을 수 없습니다."
        )

    success_count = 0
    failed_count = 0

    print("분당수서로 배치 수집을 시작합니다.")
    print(f"수집 횟수: {RUN_COUNT}회")
    print(f"수집 간격: {INTERVAL_SECONDS}초")

    for run_number in range(1, RUN_COUNT + 1):
        if run_collection(run_number):
            success_count += 1
        else:
            failed_count += 1

        # 마지막 실행 후에는 기다리지 않음
        if run_number < RUN_COUNT:
            next_time = datetime.now() + timedelta(
                seconds=INTERVAL_SECONDS
            )

            print()
            print(
                f"다음 수집 예정 시각: "
                f"{next_time:%Y-%m-%d %H:%M:%S}"
            )
            print(f"{INTERVAL_SECONDS}초 동안 대기합니다.")

            time.sleep(INTERVAL_SECONDS)

    print("\n" + "=" * 60)
    print("배치 수집 종료")
    print(f"성공: {success_count}회")
    print(f"실패: {failed_count}회")
    print("=" * 60)


if __name__ == "__main__":
    main()