# ============================================================
#  INTENT CLASSIFIER — GoClaw Layer 3
#  Tier 1: keyword match (<60 chars, 0 tokens, <1ms)
#  Tier 2: LLM classify (>60 chars or no match, max_tokens=20)
# ============================================================
import os, sys, json, time
import urllib.request
import urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

# ── Tier 1: Keyword dictionaries ──
KEYWORD_MAP = {
    "status_query": [
        "status", "đang làm gì", "dang lam gi", "bao lâu", "bao lau",
        "what doing", "xong chưa", "xong chua", "tiến độ", "tien do",
        "how long", "progress", "done yet", "đến đâu", "den dau",
        "xong chưa vậy", "xong chua vay",
        "não đâu", "nao dau", "ém xong chưa", "em xong chua",
        "soi chưa", "soi chua",
    ],
    "cancel": [
        "stop", "dừng", "dung", "thôi", "thoi", "hủy", "huy",
        "cancel", "abort", "stop it", "dừng lại", "dung lai",
        "ngưng", "ngung", "halt",
    ],
    "steer": [
        "thêm", "them", "à mà", "a ma", "nhớ", "nho",
        "cũng", "cung", "luôn nha", "luon nha",
    ],
    "test_erp": [
        "test quote", "test di", "test đi", "kiem tra quote", "kiểm tra quote",
        "chay test", "chạy test", "test erp", "thu quote", "thử quote",
        "test cai nay", "test cái này", "test het di", "test hết đi",
        "run test", "test all",
    ],
    "new_conversation": [
        "mo conversation moi", "mở conversation mới",
        "new conversation", "mo chat moi", "mở chat mới",
        "conversation moi di", "conversation mới đi",
        "reset chat", "bat dau lai", "bắt đầu lại",
    ],
    "question": [
        "là gì", "la gi", "làm gì", "lam gi", "thế nào", "the nao",
        "như nào", "nhu nao", "what is", "what does", "how does",
        "explain", "hệ thống", "he thong", "bot này", "bot nay",
        "mày là", "may la", "em là", "em la",
        "cho anh biết", "cho anh biet", "nói cho anh", "noi cho anh",
        "giải thích", "giai thich",
    ],
    "greeting": [
        "chào", "chao", "hello", "hi", "hey",
        "alo", "xin chào", "xin chao",
    ],
}


def classify(text):
    """
    Classify message intent.
    Returns: 'status_query' | 'cancel' | 'steer' | 'test_erp' |
             'new_conversation' | 'question' | 'greeting' | 'new_task'
    """
    if not text or not text.strip():
        return "new_task"

    text_clean = text.strip().lower()

    # Tier 1: Keyword match for short messages
    if len(text_clean) < 80:
        for intent, keywords in KEYWORD_MAP.items():
            for kw in keywords:
                if kw in text_clean:
                    return intent

    # Tier 2: LLM classify (for longer messages or no keyword match)
    llm_result = _llm_classify(text_clean)
    if llm_result:
        return llm_result

    # Fallback: if message looks like a continuation, treat as steer
    if len(text_clean) < 100:
        return "steer"
    return "new_task"


def _llm_classify(text):
    """
    Call Gemini API for intent classification.
    max_tokens=20, temperature=0.0, timeout=5s.
    Returns intent string or None on failure.
    """
    try:
        # Use Gemini API key from bot config if available
        api_key = _get_gemini_key()
        if not api_key:
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        prompt = (
            "Classify this message into exactly ONE word: "
            "status_query / cancel / steer / new_task\n\n"
            "Rules:\n"
            "- status_query: asking about progress, what's happening\n"
            "- cancel: wants to stop/abort current work\n"
            "- steer: adding context or modifying the current task\n"
            "- new_task: a completely new request\n\n"
            f'Message: "{text}"\n\n'
            "Reply with ONE word only:"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 20,
                "temperature": 0.0,
            }
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")

        resp = urllib.request.urlopen(req, timeout=5)
        result = json.loads(resp.read().decode("utf-8"))
        reply = result["candidates"][0]["content"]["parts"][0]["text"].strip().lower()

        # Validate response
        valid = {"status_query", "cancel", "steer", "new_task"}
        if reply in valid:
            return reply
        # Try to extract valid intent from response
        for v in valid:
            if v in reply:
                return v
        return None

    except Exception as e:
        print(f"[INTENT] LLM classify failed: {e}")
        return None


def _get_gemini_key():
    """Try to find Gemini API key from environment or config."""
    # Check environment variable
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key

    # Try to read from bot config
    try:
        bot_config_path = os.path.join(config.WORKSPACE, "TelegramBot", "config.py")
        if os.path.exists(bot_config_path):
            with open(bot_config_path, "r", encoding="utf-8") as f:
                content = f.read()
            import re
            match = re.search(r'GEMINI_API_KEY\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except Exception:
        pass

    return None
