"""
Neon DB 수동 백업 스크립트

사용법:
  python backup.py

결과:
  backups/backup_YYYY-MM-DD_HH-MM.json.gz 파일 생성

실행 조건:
  pip install psycopg2-binary python-dotenv
  .env 파일에 DATABASE_URL 설정 필요 (Render 환경변수 값 복사)
"""

import os
import json
import gzip
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

TABLES = ["users", "channels", "videos", "ab_tests", "variations", "metrics_logs", "api_quota_usage"]

BACKUP_DIR = os.path.join(os.path.dirname(__file__), "backups")


def backup():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL 환경변수가 없습니다. .env 파일을 확인해주세요.")
        return

    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        logger.error("psycopg2-binary 가 설치되지 않았습니다: pip install psycopg2-binary")
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
    filename = os.path.join(BACKUP_DIR, f"backup_{timestamp}.json.gz")

    logger.info(f"Neon DB 백업 시작 → {filename}")

    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        backup_data = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tables": {}
        }

        for table in TABLES:
            try:
                cur.execute(f"SELECT * FROM {table}")
                rows = cur.fetchall()
                # datetime → ISO 문자열 변환
                serialized = []
                for row in rows:
                    serialized.append({
                        k: (v.isoformat() if hasattr(v, "isoformat") else v)
                        for k, v in dict(row).items()
                    })
                backup_data["tables"][table] = serialized
                logger.info(f"  ✓ {table}: {len(serialized)}행")
            except Exception as e:
                logger.warning(f"  ✗ {table} 백업 실패: {e}")
                backup_data["tables"][table] = []

        cur.close()
        conn.close()

        with gzip.open(filename, "wt", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)

        size_kb = os.path.getsize(filename) / 1024
        logger.info(f"백업 완료: {filename} ({size_kb:.1f} KB)")

        # 30일 이상 된 백업 파일 자동 삭제
        _cleanup_old_backups(days=30)

    except Exception as e:
        logger.error(f"백업 실패: {e}")
        raise


def _cleanup_old_backups(days: int = 30):
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    removed = 0
    for fname in os.listdir(BACKUP_DIR):
        fpath = os.path.join(BACKUP_DIR, fname)
        if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
            os.remove(fpath)
            removed += 1
    if removed:
        logger.info(f"오래된 백업 {removed}개 삭제 완료 ({days}일 기준)")


if __name__ == "__main__":
    backup()
