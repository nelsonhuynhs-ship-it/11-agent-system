"""
test_health.py — Kiểm tra các API endpoints cơ bản
===================================================
Chạy: pytest api/tests/ -v
Không cần VPS, không cần Parquet — test syntax & logic thuần
"""
import sys
import os
import pytest

# ── Đường dẫn ────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Test 1: Các file quan trọng phải tồn tại ─────────────────
class TestCriticalFiles:
    """Kiểm tra các file cốt lõi không bị mất"""

    BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def test_email_rate_router_exists(self):
        path = os.path.join(self.BASE, "api", "routers", "email_rate_router.py")
        assert os.path.exists(path), f"MISSING: {path}"

    def test_health_router_exists(self):
        path = os.path.join(self.BASE, "api", "routers", "health_router.py")
        assert os.path.exists(path), f"MISSING: {path}"

    def test_cnee_master_exists(self):
        path = os.path.join(self.BASE, "email_engine", "data", "cnee_master.xlsx")
        assert os.path.exists(path), f"MISSING: cnee_master.xlsx — campaign list sẽ trống"

    def test_customer_rules_exists(self):
        path = os.path.join(self.BASE, "email_engine", "data", "customer_rules.json")
        assert os.path.exists(path), f"MISSING: customer_rules.json"

    def test_email_log_exists(self):
        path = os.path.join(self.BASE, "email_engine", "logs", "email_log.csv")
        assert os.path.exists(path), f"MISSING: email_log.csv"


# ── Test 2: Python syntax check ───────────────────────────────
class TestSyntax:
    """Kiểm tra không có lỗi cú pháp trong các file quan trọng"""

    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _compile_check(self, filepath):
        import py_compile
        try:
            py_compile.compile(filepath, doraise=True)
            return True
        except py_compile.PyCompileError as e:
            pytest.fail(f"Syntax error in {filepath}: {e}")

    def test_email_rate_router_syntax(self):
        self._compile_check(os.path.join(self.BASE, "routers", "email_rate_router.py"))

    def test_health_router_syntax(self):
        self._compile_check(os.path.join(self.BASE, "routers", "health_router.py"))

    def test_all_routers_syntax(self):
        routers_dir = os.path.join(self.BASE, "routers")
        for f in os.listdir(routers_dir):
            if f.endswith(".py") and not f.endswith(".bak"):
                self._compile_check(os.path.join(routers_dir, f))


# ── Test 3: Kiểm tra data files không bị corrupt ─────────────
class TestDataIntegrity:
    """Kiểm tra data files đọc được"""

    BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def test_cnee_master_readable(self):
        try:
            import pandas as pd
            path = os.path.join(self.BASE, "email_engine", "data", "cnee_master.xlsx")
            if os.path.exists(path):
                df = pd.read_excel(path)
                assert len(df) > 0, "cnee_master.xlsx trống!"
                assert len(df) >= 5000, f"cnee_master.xlsx chỉ có {len(df)} rows — có thể bị mất data"
        except ImportError:
            pytest.skip("pandas not available")

    def test_email_log_readable(self):
        try:
            import pandas as pd
            path = os.path.join(self.BASE, "email_engine", "logs", "email_log.csv")
            if os.path.exists(path):
                df = pd.read_csv(path)
                required_cols = {"timestamp", "email", "subject", "status"}
                assert required_cols.issubset(set(df.columns)), \
                    f"email_log.csv thiếu columns: {required_cols - set(df.columns)}"
        except ImportError:
            pytest.skip("pandas not available")

    def test_customer_rules_json_valid(self):
        import json
        path = os.path.join(self.BASE, "email_engine", "data", "customer_rules.json")
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            assert isinstance(data, dict), "customer_rules.json không phải dict"

    def test_parquet_exists_if_rate_feature_active(self):
        """Nếu parquet không có thì rate query sẽ fail — cảnh báo sớm"""
        parquet_path = os.path.join(
            self.BASE, "Pricing_Engine", "data", "Cleaned_Master_History.parquet"
        )
        if not os.path.exists(parquet_path):
            pytest.skip("Parquet file không có trên CI — bình thường (file lớn không commit)")


# ── Test 4: Config & environment ─────────────────────────────
class TestConfig:
    """Kiểm tra config cơ bản"""

    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_env_file_exists(self):
        """Ít nhất phải có .env hoặc config.py"""
        env_path = os.path.join(self.BASE, ".env")
        config_path = os.path.join(self.BASE, "config.py")
        has_env = os.path.exists(env_path)
        has_config = os.path.exists(config_path)
        assert has_env or has_config, "Thiếu cả .env và config.py — API sẽ không chạy được"

    def test_main_py_exists(self):
        path = os.path.join(self.BASE, "app.py")
        assert os.path.exists(path), "MISSING: api/app.py — FastAPI entry point"

    def test_main_py_syntax(self):
        import py_compile
        path = os.path.join(self.BASE, "app.py")
        if os.path.exists(path):
            try:
                py_compile.compile(path, doraise=True)
            except py_compile.PyCompileError as e:
                pytest.fail(f"Syntax error in main.py: {e}")
