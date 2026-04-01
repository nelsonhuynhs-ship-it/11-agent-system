# ============================================================
#  CTO Agent — Shared Configuration
#  All subagents import from here
# ============================================================
import os

# Workspace
WORKSPACE = os.path.normpath(r"D:\NELSON\2. Areas\PricingSystem\Engine_test")
AGENT_DIR = os.path.join(WORKSPACE, ".agent")
AGENTS_DIR = os.path.join(AGENT_DIR, "agents")
MEMORY_DIR = os.path.join(AGENT_DIR, "memory")
BACKUP_DIR = os.path.join(AGENT_DIR, "backup")
LISTENER_DIR = os.path.join(AGENT_DIR, "listener")

# Telegram
BOT_TOKEN = "8697753100:AAF0HVN0VxK-ilyz_GUdE_JOCSr3D3QCFys"
NELSON_CHAT_ID = 5398948978
CHAT_ID = NELSON_CHAT_ID  # alias for convenience

# Gemini API
GEMINI_API_KEY = "AIzaSyCR0sqBU9TH6ApfWuAdoTEAPbPfmQ9CKQ8"

AGENT_MODELS = {
    "NÃO":  "gemini-3.1-flash-lite-preview",
    "ÉM":   "gemini-3.1-flash-lite-preview",
    "SOI":  "gemini-3.1-flash-lite-preview",
    "LÍNH": "rule-based",
    "Ổ":    "rule-based",
    "NÓI":  "rule-based",
}

# ERP
ERP_VERSION = "V13"
ERP_STAGING = os.path.join(WORKSPACE, "ERP", "data", "ERP_V13_STAGING.xlsm")
VBA_DIR = os.path.join(WORKSPACE, "ERP", "vba")
BUILD_SCRIPT = os.path.join(WORKSPACE, "ERP", "core", "build_erp_v13_ribbon.py")

# Context files
ACTIVE_CONTEXT = os.path.join(MEMORY_DIR, "05_active_context.md")
SESSION_LOG = os.path.join(MEMORY_DIR, "session_log.md")

# ── GUARD RULES (hardcoded, cannot be overridden) ──

# Protected extensions — NEVER delete files with these
PROTECTED_EXTENSIONS = {".bas", ".py", ".xlsm", ".json", ".md", ".ps1"}

# Read-only files — NEVER modify directly
READ_ONLY_FILES = {
    os.path.join(WORKSPACE, "ERP", "data", "ERP_Master.xlsm"),
}

# Forbidden commands — NEVER execute
FORBIDDEN_COMMANDS = [
    "rm -rf", "del /f /s", "DROP TABLE", "TRUNCATE", "format",
    "Remove-Item -Recurse -Force",
]

# Max diff percentage before requiring approval
MAX_DIFF_PERCENT = 40

# Ensure directories exist
for d in [AGENT_DIR, AGENTS_DIR, MEMORY_DIR, BACKUP_DIR, LISTENER_DIR]:
    os.makedirs(d, exist_ok=True)


# ── LLM Helper ──

def call_llm(prompt, agent="NÃO", max_tokens=8192, temperature=0.1):
    """Call Gemini API for any agent that needs LLM reasoning."""
    model_name = AGENT_MODELS.get(agent, "gemini-2.5-pro-exp-03-25")
    if model_name == "rule-based":
        return None  # Rule-based agents don't call LLM

    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        return response.text
    except ImportError:
        print("[CONFIG] google-genai not installed")
        return None
    except Exception as e:
        print(f"[CONFIG] LLM call failed: {e}")
        return None
