# ============================================================
#  BROWSER BOT — N.E.L.S.O.N AI OS Workstation
#  Automates Claude.ai browser via Selenium + existing Chrome profile
#  Triggers: "mở conversation mới" / "new conversation"
# ============================================================
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

AGENT = "ÉM"
CHROME_PROFILE = r"C:\ChromeProfile\Nelson"
CLAUDE_URL = "https://claude.ai/new"
ACTIVE_CONTEXT = os.path.join(config.MEMORY_DIR, "05_active_context.md")


class BrowserBot:
    """Automates Claude.ai browser sessions."""

    def __init__(self):
        self.driver = None

    def _start_driver(self):
        """Start Chrome with existing logged-in profile."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            opts = Options()
            opts.add_argument(f"--user-data-dir={CHROME_PROFILE}")
            opts.add_argument("--no-first-run")
            opts.add_argument("--no-default-browser-check")
            self.driver = webdriver.Chrome(options=opts)
            print(f"[{AGENT}] Chrome started with profile: {CHROME_PROFILE}")
        except ImportError:
            print(f"[{AGENT}] selenium not installed. Run: pip install selenium")
            raise
        except Exception as e:
            print(f"[{AGENT}] Chrome start error: {e}")
            raise

    def _quit_driver(self):
        """Quit Chrome safely."""
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        self.driver = None

    def load_active_context(self):
        """Read active context for session restore."""
        if os.path.exists(ACTIVE_CONTEXT):
            with open(ACTIVE_CONTEXT, "r", encoding="utf-8") as f:
                return f"[SESSION RESTORE]\n{f.read()}"
        return "[SESSION RESTORE]\nNo active context found."

    def open_new_conversation(self, initial_message=None):
        """
        Open claude.ai, start new chat, optionally send opening message.
        Returns conversation URL.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        if not self.driver:
            self._start_driver()

        self.driver.get(CLAUDE_URL)
        time.sleep(3)

        if initial_message:
            try:
                wait = WebDriverWait(self.driver, 15)
                # Try multiple selectors for the input box
                selectors = [
                    '[data-testid="chat-input"]',
                    'div[contenteditable="true"]',
                    'textarea',
                    '.ProseMirror',
                ]
                input_box = None
                for sel in selectors:
                    try:
                        input_box = wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                        )
                        break
                    except Exception:
                        continue

                if input_box:
                    context = self.load_active_context()
                    full_msg = f"{context}\n\n{initial_message}"
                    input_box.send_keys(full_msg)
                    time.sleep(0.5)

                    # Try to find and click send button
                    send_btns = self.driver.find_elements(
                        By.CSS_SELECTOR, 'button[type="submit"], button[aria-label="Send"]'
                    )
                    if send_btns:
                        send_btns[0].click()
                    print(f"[{AGENT}] Message sent to Claude")
                else:
                    print(f"[{AGENT}] Could not find input box")

            except Exception as e:
                print(f"[{AGENT}] Input error: {e}")

        url = self.driver.current_url
        print(f"[{AGENT}] New conversation: {url}")
        return url

    def close_old_and_open_new(self, message=None):
        """Close current and open new conversation with context."""
        self._quit_driver()
        time.sleep(1)
        new_url = self.open_new_conversation(message)

        # Notify Nelson via notifier
        try:
            import notifier
            notifier.send(
                f"NÓI: Conversation mới đã mở.\n"
                f"Context loaded từ active_context.md\n"
                f"URL: {new_url}"
            )
        except Exception as e:
            print(f"[{AGENT}] Notifier error: {e}")

        return new_url

    def take_screenshot(self, name="browser"):
        """Capture browser screenshot."""
        if not self.driver:
            return None
        screenshot_dir = os.path.join(config.WORKSPACE, ".agent", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(screenshot_dir, f"{ts}_{name}.png")
        self.driver.save_screenshot(path)
        print(f"[{AGENT}] Browser screenshot: {path}")
        return path


# Convenience functions
def new_conversation(message=None):
    """Open new Claude conversation with active context."""
    bot = BrowserBot()
    return bot.close_old_and_open_new(message)


def open_url(url):
    """Open any URL in browser."""
    bot = BrowserBot()
    if not bot.driver:
        bot._start_driver()
    bot.driver.get(url)
    return bot.driver.current_url
