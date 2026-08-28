"""Redis connection singleton (lazy). None when REDIS_URL is not configured."""
import os

import redis

REDIS_URL = os.getenv("REDIS_URL")

redis_conn = redis.Redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None
