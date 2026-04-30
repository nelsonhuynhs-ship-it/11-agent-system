"""Email sender backends: outlook (COM) | graph (Microsoft Graph API)."""
from .graph_sender import send_html_via_graph, get_token, verify_in_sent_folder

__all__ = ["send_html_via_graph", "get_token", "verify_in_sent_folder"]
