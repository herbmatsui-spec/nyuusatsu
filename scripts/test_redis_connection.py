import os
import redis
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RedisTest")

def test_connection():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    logger.info(f"Testing connection to Redis at: {redis_url}")
    try:
        r = redis.from_url(redis_url, decode_responses=True)
        # Some Redis versions (like older Windows ports/Memurai) might not support HELLO
        # but ping() should work. If redis-py is using HELLO internally for version check,
        # we try to force a simple ping.
        try:
            if r.ping():
                logger.info("Successfully connected to Redis!")
                return True
        except redis.exceptions.ResponseError as e:
            if "unknown command 'HELLO'" in str(e):
                logger.info("Redis server does not support HELLO, but is responding. Considering it connected.")
                return True
            raise e
            logger.info("Successfully connected to Redis!")
            return True
    except Exception as e:
        logger.error(f"Connection failed: {e}")
    return False

if __name__ == "__main__":
    if test_connection():
        print("SUCCESS")
    else:
        print("FAILURE")
        exit(1)
