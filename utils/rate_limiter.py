import time
import threading
from dataclasses import dataclass
from config import AppConfig

@dataclass
class RateLimitConfig:
    requests_per_minute: int = 60
    tokens_per_minute: int = 100000

class RateLimiter:
    """
    Token Bucket algorithm to limit API requests and tokens.
    """
    def __init__(self, requests_limit: int, tokens_limit: int):
        self.requests_limit = requests_limit
        self.tokens_limit = tokens_limit
        self.requests_bucket = requests_limit
        self.tokens_bucket = tokens_limit
        self.last_update = time.time()
        self.lock = threading.Lock()

    def _update_buckets(self):
        now = time.time()
        elapsed = now - (self.last_update - now) # Simplified for logic
        # Actually:
        elapsed = now - self.last_update
        
        # Add tokens based on time elapsed
        self.requests_bucket = min(
            self.requests_limit, 
            self.requests_bucket + elapsed * (self.requests_limit / 60.0)
        )
        self.tokens_bucket = min(
            self.tokens_limit, 
            self.tokens_bucket + elapsed * (self.tokens_limit / 60.0)
        )
        self.last_update = now

    def consume(self, tokens: int = 1):
        with self.lock:
            while True:
                self._update_buckets()
                if self.requests_bucket >= 1 and self.tokens_bucket >= tokens:
                    self.requests_bucket -= 1
                    self.tokens_bucket -= tokens
                    return True
                
                # Wait for tokens to refill
                sleep_time = 1.0
                time.sleep(sleep_time)
                return False # Or block. For simplicity in sync, we block.

    def wait_and_consume(self, tokens: int = 1):
        with self.lock:
            while True:
                self._update_buckets()
                if self.requests_bucket >= 1 and self.tokens_bucket >= tokens:
                    self.requests_bucket -= 1
                    self.tokens_bucket -= tokens
                    return
                time.sleep(0.5)

# Global limiters
deepseek_limiter = RateLimiter(60, 100000)
gemini_limiter = RateLimiter(15, 1000000)
