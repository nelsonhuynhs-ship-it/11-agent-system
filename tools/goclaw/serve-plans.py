# -*- coding: utf-8 -*-
"""
serve-plans.py — Simple HTTP server for D:/GoClaw-plans/ directory.

Serves HTML plan files on port 8765. Started automatically by publish-plan.bat.
Safe to run multiple times — will exit if port is already bound.

Index page auto-lists recent plans sorted by modification time.

Usage:
    python serve-plans.py                # Blocking server
    start /b python serve-plans.py       # Background (from batch)
"""
import html as html_mod
import os
import socket
import sys
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PLANS_DIR = Path(r"D:/GoClaw-plans")
PORT = 8765


def port_in_use(port: int) -> bool:
    """Check if a TCP port is already bound on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


class PlansHandler(SimpleHTTPRequestHandler):
    """HTTP handler serving plans dir with UTF-8 headers and auto-index."""

    # Force UTF-8 content types
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
        ".json": "application/json; charset=utf-8",
    }

    def log_message(self, format, *args):
        """Silence default access logs to keep Fox exec output clean."""
        pass

    def list_directory(self, path):
        """Custom index page listing HTML plans sorted by mtime desc."""
        try:
            entries = [p for p in Path(path).iterdir() if p.is_file() and p.suffix == ".html"]
        except OSError:
            self.send_error(404, "Directory not found")
            return None

        entries.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        rows = []
        for p in entries:
            mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            size_kb = p.stat().st_size // 1024
            rows.append(
                f'<tr class="border-b border-slate-100 hover:bg-slate-50">'
                f'<td class="px-4 py-2"><a class="text-blue-600 hover:underline" href="{html_mod.escape(p.name)}">{html_mod.escape(p.name)}</a></td>'
                f'<td class="px-4 py-2 text-slate-500 text-sm">{mtime}</td>'
                f'<td class="px-4 py-2 text-slate-400 text-sm text-right">{size_kb} KB</td>'
                f'</tr>'
            )

        if not rows:
            rows.append(
                '<tr><td colspan="3" class="px-4 py-6 text-center text-slate-400">Chưa có plan nào. Fox Spirit sẽ publish ở đây.</td></tr>'
            )

        body = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GoClaw Plans • Nelson Freight</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; }}</style>
</head>
<body class="bg-gradient-to-br from-slate-50 to-blue-50 min-h-screen">
<div class="max-w-4xl mx-auto px-4 py-8">
  <header class="mb-6">
    <h1 class="text-3xl font-bold text-slate-900 mb-1">🦊 GoClaw Plans</h1>
    <p class="text-slate-500">Plans aggregated by Fox Spirit from nelson-ops-team</p>
  </header>
  <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
    <table class="w-full">
      <thead class="bg-slate-100 border-b border-slate-200">
        <tr>
          <th class="px-4 py-2 text-left text-sm font-semibold text-slate-700">Plan</th>
          <th class="px-4 py-2 text-left text-sm font-semibold text-slate-700">Generated</th>
          <th class="px-4 py-2 text-right text-sm font-semibold text-slate-700">Size</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </div>
  <footer class="mt-6 text-center text-xs text-slate-400">
    serve-plans.py • port {PORT}
  </footer>
</div>
</body>
</html>"""
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        # Return a file-like object for the base class to copy
        import io
        return io.BytesIO(encoded)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    if port_in_use(PORT):
        print(f"Port {PORT} already in use — server is already running.")
        return 0

    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    os.chdir(PLANS_DIR)

    server = HTTPServer(("0.0.0.0", PORT), PlansHandler)
    print(f"Serving {PLANS_DIR} on http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
        print("Server stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
