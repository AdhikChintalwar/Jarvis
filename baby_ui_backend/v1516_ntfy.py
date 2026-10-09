from __future__ import annotations

import os
import urllib.request

from .v1516_quick import issue_setup_token


class SecureNtfy:
    def __init__(self):
        self.enabled = os.getenv("BABY_NTFY_ENABLED", "false").lower() == "true"
        self.base = (os.getenv("BABY_NTFY_BASE_URL") or "").rstrip("/")
        self.topic = (os.getenv("BABY_NTFY_TOPIC") or "").strip()
        self.token = (os.getenv("BABY_NTFY_TOKEN") or "").strip()
        self.quick_base = (os.getenv("BABY_QUICK_PUBLIC_URL") or "").rstrip("/")

    def publish(self, title, message, symbol=None, episode=None, priority="high", tags="chart_with_upwards_trend"):
        if not (self.enabled and self.base and self.topic and self.token):
            return {"sent": False, "reason": "SECURE_NTFY_NOT_CONFIGURED"}
        headers = {
            "Title": title,
            "Priority": priority,
            "Tags": tags,
            "Authorization": f"Bearer {self.token}",
        }
        if symbol and episode and self.quick_base:
            token = issue_setup_token(symbol, int(episode), 15)
            headers["Click"] = f"{self.quick_base}/quick/s/{token}"
        request = urllib.request.Request(
            f"{self.base}/{self.topic}", data=message.encode(), method="POST", headers=headers
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            return {"sent": 200 <= response.status < 300, "status": response.status}


secure_ntfy = SecureNtfy()
