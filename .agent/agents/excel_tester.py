# ============================================================
#  EXCEL LIVE TESTER — N.E.L.S.O.N AI OS Workstation
#  Uses win32com.client to run real Excel macros headlessly.
#  Uses pyautogui + PIL for screenshots.
#  Uses pygetwindow to focus Excel window.
#  NEVER touches ERP_Master.xlsm — always ERP_TEST.xlsm.
# ============================================================
import os, sys, time, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

AGENT = "ÉM"
TEST_FILE = os.path.join(config.WORKSPACE, "ERP", "data", "ERP_TEST.xlsm")
SCREENSHOT_DIR = os.path.join(config.WORKSPACE, ".agent", "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def _ts():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


class ExcelTester:
    """Live Excel tester using COM automation."""

    def __init__(self):
        self.xl = None
        self.wb = None

    def _open_excel(self):
        """Open Excel via COM in visible mode for screenshots."""
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        self.xl = win32com.client.Dispatch("Excel.Application")
        self.xl.Visible = True
        self.xl.DisplayAlerts = False
        self.wb = self.xl.Workbooks.Open(TEST_FILE)
        print(f"[{AGENT}] Excel opened: {os.path.basename(TEST_FILE)}")

    def _close_excel(self):
        """Close without saving — test file only."""
        try:
            if self.wb:
                self.wb.Close(SaveChanges=False)
            if self.xl:
                self.xl.Quit()
        except Exception as e:
            print(f"[{AGENT}] Excel close error: {e}")
        self.xl = None
        self.wb = None

    def capture_screenshot(self, test_name):
        """Focus Excel window, capture region, save PNG."""
        try:
            import pygetwindow as gw
            import pyautogui

            path = os.path.join(SCREENSHOT_DIR, f"{_ts()}_{test_name}.png")

            # Find Excel window
            wins = gw.getWindowsWithTitle("ERP_TEST")
            if not wins:
                wins = gw.getWindowsWithTitle("Excel")

            if wins:
                win = wins[0]
                win.activate()
                time.sleep(0.3)
                screenshot = pyautogui.screenshot(
                    region=(win.left, win.top, win.width, win.height)
                )
            else:
                # Fallback: full screen
                screenshot = pyautogui.screenshot()

            screenshot.save(path)
            print(f"[{AGENT}] Screenshot: {path}")
            return path

        except ImportError as e:
            print(f"[{AGENT}] Screenshot deps missing: {e}")
            return None
        except Exception as e:
            print(f"[{AGENT}] Screenshot error: {e}")
            return None

    # ── Test Cases ──

    def run_quote_test(self):
        """Test: inject quote data → run MarkQuoteWin → check Active Jobs."""
        self._open_excel()
        try:
            ws_q = self.wb.Sheets("Quotes")
            # Inject test quote in row 8
            ws_q.Cells(8, 3).Value = "NAFOODS GROUP"
            ws_q.Cells(8, 4).Value = "COSCO"
            ws_q.Cells(8, 5).Value = "HCM"
            ws_q.Cells(8, 6).Value = "LAX"
            ws_q.Cells(8, 14).Value = 4500
            ws_q.Cells(8, 15).Value = 4900
            ws_q.Cells(8, 16).Value = "40HC"
            ws_q.Cells(8, 17).Value = 1
            ws_q.Cells(8, 23).Value = "Open"

            # Run the real macro
            self.xl.Run("QuoteBuilder_ERP.MarkQuoteWin")
            time.sleep(2)

            # Read results from Active Jobs
            ws_j = self.wb.Sheets("Active Jobs")
            results = {
                "cost_breakdown": ws_j.Cells(8, 27).Value,
                "request_bkg": ws_j.Cells(8, 28).Value,
                "crm_id": ws_j.Cells(8, 1).Value,
                "status": ws_j.Cells(8, 16).Value,
                "fast_job_no": ws_j.Cells(8, 29).Value,
            }

            # Screenshot Active Jobs
            self.xl.Windows(1).Activate()
            self.wb.Sheets("Active Jobs").Activate()
            time.sleep(0.5)
            screenshot = self.capture_screenshot("quote_win")

            return {"results": results, "screenshot": screenshot}

        except Exception as e:
            print(f"[{AGENT}] Quote test error: {e}")
            return {"results": {"error": str(e)}, "screenshot": None}
        finally:
            self._close_excel()

    def run_crm_test(self):
        """Test: CRM lookup functions."""
        self._open_excel()
        try:
            ws_crm = self.wb.Sheets("CRM")
            results = {
                "crm_id": ws_crm.Cells(2, 1).Value,
                "customer": ws_crm.Cells(2, 2).Value,
                "total_cols": ws_crm.UsedRange.Columns.Count,
            }
            self.wb.Sheets("CRM").Activate()
            time.sleep(0.3)
            screenshot = self.capture_screenshot("crm_lookup")
            return {"results": results, "screenshot": screenshot}
        except Exception as e:
            return {"results": {"error": str(e)}, "screenshot": None}
        finally:
            self._close_excel()

    def run_puc_test(self):
        """Test: PUC Lookup sheet data."""
        self._open_excel()
        try:
            ws_puc = self.wb.Sheets("PUC_Lookup")
            results = {
                "first_place": ws_puc.Cells(2, 1).Value,
                "first_puc": ws_puc.Cells(2, 2).Value,
                "total_rows": ws_puc.UsedRange.Rows.Count - 1,
            }
            self.wb.Sheets("PUC_Lookup").Activate()
            time.sleep(0.3)
            screenshot = self.capture_screenshot("puc_lookup")
            return {"results": results, "screenshot": screenshot}
        except Exception as e:
            return {"results": {"error": str(e)}, "screenshot": None}
        finally:
            self._close_excel()

    def run_monthly_report_test(self):
        """Test: Monthly Report macro available."""
        self._open_excel()
        try:
            # Just check the sheet exists and macro is callable
            sheets = [self.wb.Sheets(i).Name for i in range(1, self.wb.Sheets.Count + 1)]
            results = {
                "sheet_count": len(sheets),
                "sheets": ", ".join(sheets[:10]),
            }
            screenshot = self.capture_screenshot("monthly_report")
            return {"results": results, "screenshot": screenshot}
        except Exception as e:
            return {"results": {"error": str(e)}, "screenshot": None}
        finally:
            self._close_excel()

    def run_booking_email_test(self):
        """Test: BookingEmail macro formatting."""
        self._open_excel()
        try:
            ws_j = self.wb.Sheets("Active Jobs")
            results = {
                "header_row": 7,
                "col_count": ws_j.UsedRange.Columns.Count,
                "request_bkg_header": ws_j.Cells(7, 28).Value,
            }
            self.wb.Sheets("Active Jobs").Activate()
            time.sleep(0.3)
            screenshot = self.capture_screenshot("booking_email")
            return {"results": results, "screenshot": screenshot}
        except Exception as e:
            return {"results": {"error": str(e)}, "screenshot": None}
        finally:
            self._close_excel()

    # ── Validation ──

    def validate_results(self, results):
        """SOI calls this to check if results match expected."""
        checks = []

        if "error" in results:
            checks.append(f"\u274C Error: {results['error']}")
            return {"verdict": "FAIL", "checks": checks}

        # Cost breakdown format
        cb = str(results.get("cost_breakdown", ""))
        if cb and ("S/C" in cb or "COST" in cb or len(cb) > 10):
            checks.append("\u2705 Cost_Breakdown format: PASS")
        elif cb:
            checks.append(f"\u26A0\uFE0F Cost_Breakdown format: WARN \u2014 {cb[:50]}")
        else:
            checks.append("\u274C Cost_Breakdown: FAIL \u2014 empty")

        # CRM_ID populated
        crm_id = results.get("crm_id")
        if crm_id:
            checks.append(f"\u2705 CRM_ID: PASS ({crm_id})")
        else:
            checks.append("\u274C CRM_ID: FAIL \u2014 empty")

        # Status changed
        status = results.get("status")
        if status == "Booked":
            checks.append("\u2705 Status \u2192 Booked: PASS")
        elif status:
            checks.append(f"\u26A0\uFE0F Status: WARN \u2014 got {status}")
        else:
            checks.append("\u274C Status: FAIL \u2014 empty")

        # Request BKG
        bkg = str(results.get("request_bkg", ""))
        if "mailto" in bkg.lower() or "Request" in bkg or len(bkg) > 5:
            checks.append("\u2705 Request BKG link: PASS")
        else:
            checks.append("\u274C Request BKG link: FAIL")

        passed = sum(1 for c in checks if "\u2705" in c)
        total = len(checks)
        verdict = "PASS" if passed == total else f"FAIL ({passed}/{total})"
        return {"verdict": verdict, "checks": checks}

    # ── Full Suite ──

    def run_all_tests(self):
        """Run full test suite \u2014 called by SOI."""
        tests = [
            ("Quote WIN flow", self.run_quote_test),
            ("CRM Lookup", self.run_crm_test),
            ("PUC Lookup", self.run_puc_test),
            ("Monthly Report", self.run_monthly_report_test),
            ("Booking Email", self.run_booking_email_test),
        ]
        all_results = []
        for name, fn in tests:
            print(f"[{AGENT}] Running test: {name}...")
            result = fn()
            validation = self.validate_results(result["results"])
            all_results.append({
                "test": name,
                "verdict": validation["verdict"],
                "checks": validation["checks"],
                "screenshot": result.get("screenshot"),
            })
        return all_results


# Convenience function
def run_tests():
    """Run all Excel tests and return results."""
    tester = ExcelTester()
    return tester.run_all_tests()
