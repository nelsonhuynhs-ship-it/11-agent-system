"""
Sprint 5: Rate Limiter for Gemini AI
Tracks API usage and prevents exceeding free tier limits.
"""
import time
from collections import deque
from config import GEMINI_MODEL

# Free tier limits per model (from Google AI Studio dashboard)
MODEL_LIMITS = {
    "gemini-2.5-flash": {"rpm": 5, "rpd": 20, "tpm": 250000},
    "gemini-2.5-flash-lite": {"rpm": 10, "rpd": 20, "tpm": 250000},
    "gemini-3-flash-preview": {"rpm": 5, "rpd": 20, "tpm": 250000},
    "gemini-3.1-flash-lite-preview": {"rpm": 15, "rpd": 500, "tpm": 250000},
    "gemini-2.0-flash-001": {"rpm": 10, "rpd": 500, "tpm": 250000},
}

# Fallback limits
DEFAULT_LIMITS = {"rpm": 5, "rpd": 20, "tpm": 250000}


class RateLimiter:
    """Track and enforce API rate limits."""
    
    def __init__(self, model_name=None):
        self.model = model_name or GEMINI_MODEL
        limits = MODEL_LIMITS.get(self.model, DEFAULT_LIMITS)
        self.rpm_limit = limits["rpm"]
        self.rpd_limit = limits["rpd"]
        
        # Request timestamps
        self._minute_requests = deque()  # timestamps within last 60s
        self._day_requests = deque()     # timestamps within last 24h
    
    def _clean_old(self):
        """Remove expired timestamps."""
        now = time.time()
        # Clean minute window
        while self._minute_requests and (now - self._minute_requests[0]) > 60:
            self._minute_requests.popleft()
        # Clean day window
        while self._day_requests and (now - self._day_requests[0]) > 86400:
            self._day_requests.popleft()
    
    def can_request(self):
        """Check if we can make a request without exceeding limits."""
        self._clean_old()
        if len(self._minute_requests) >= self.rpm_limit:
            return False, f"⏳ Rate limit: {self.rpm_limit} requests/phút. Thử lại sau {self.wait_seconds():.0f}s."
        if len(self._day_requests) >= self.rpd_limit:
            return False, f"📊 Đã dùng hết {self.rpd_limit} AI requests hôm nay. Reset lúc nửa đêm UTC."
        return True, ""
    
    def record_request(self):
        """Record a successful API request."""
        now = time.time()
        self._minute_requests.append(now)
        self._day_requests.append(now)
    
    def wait_seconds(self):
        """How long to wait before next request is allowed."""
        if not self._minute_requests:
            return 0
        oldest = self._minute_requests[0]
        return max(0, 60 - (time.time() - oldest))
    
    def usage_stats(self):
        """Get current usage statistics."""
        self._clean_old()
        return {
            "minute_used": len(self._minute_requests),
            "minute_limit": self.rpm_limit,
            "day_used": len(self._day_requests),
            "day_limit": self.rpd_limit,
            "model": self.model,
        }
    
    def usage_text(self):
        """Human-readable usage status."""
        stats = self.usage_stats()
        return (
            f"🤖 AI: {stats['model']}\n"
            f"📊 Hôm nay: {stats['day_used']}/{stats['day_limit']} requests\n"
            f"⏱️ Phút này: {stats['minute_used']}/{stats['minute_limit']} RPM"
        )


# Global instance
rate_limiter = RateLimiter()
