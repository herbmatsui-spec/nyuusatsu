import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_migration():
    """
    Alembicを使用してデータベースマイグレーションを実行する。
    """
    logger.info("Starting database migrations...")
    try:
        # alembic upgrade head を実行して最新の状態に更新
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info("Migration successful:\n%s", result.stdout)
        
        # === Seeder 実行 ===
        try:
            from database.seeders.qualification_tag_seeder import seed_qualification_tags
            from database.engine import SessionLocal
            s = SessionLocal()
            try:
                seed_qualification_tags(s)
                logger.info("Qualification tag seed completed.")
            finally:
                s.close()
        except Exception as seed_err:
            logger.warning("Seeder failed (non-fatal): %s", seed_err)
            
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Migration failed:\n%s", e.stderr)
        return False

if __name__ == "__main__":
    if run_migration():
        logger.info("Database is up to date.")
    else:
        logger.error("Database migration failed. Please check the logs.")
        sys.exit(1)
