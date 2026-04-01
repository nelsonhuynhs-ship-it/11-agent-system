import http.server, os, socketserver

os.chdir(r"D:\NELSON\2. Areas\PricingSystem\Engine_test\.agent\miniapp")

class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()
    def log_message(self, *args): pass

print("Mini App: http://localhost:8200")
socketserver.TCPServer(("0.0.0.0", 8200), Handler).serve_forever()
