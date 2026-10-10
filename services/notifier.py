"""
Notification Service.
Sends automated alerts via Telegram Bot Webhooks or Email when high-conviction signals trigger:
- Promoter SAST buying disclosures
- Consensus expectation surprise beats (>+15%)
- Governance red-flag warnings (Pledge >20%, auditor resignation)
"""
import os
import requests
from typing import Dict, Any, Optional


class NotifierService:
    """Handles real-time alerts via Telegram and Email."""

    def __init__(self, telegram_token: Optional[str] = None, telegram_chat_id: Optional[str] = None):
        self.telegram_token = telegram_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID")

    def send_telegram_alert(self, message: str) -> bool:
        """Send message via Telegram Bot API."""
        if not self.telegram_token or not self.telegram_chat_id:
            print(f"[NotifierService] Telegram credentials not configured. Alert logged locally: {message}")
            return False

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }

        try:
            r = requests.post(url, json=payload, timeout=5)
            return r.status_code == 200
        except Exception as e:
            print(f"[NotifierService] Telegram alert failed: {e}")
            return False

    def notify_high_conviction_signal(self, symbol: str, stance: str, score: float, catalyst: str):
        """Format and send high-conviction signal notification."""
        msg = (
            f"🚨 *STOCK TRAJECTORY ALERT* 🚨\n\n"
            f"📈 *Stock*: `{symbol}`\n"
            f"🎯 *Stance*: *{stance}*\n"
            f"📊 *Score*: `{score}/100`\n"
            f"💡 *Catalyst*: {catalyst}\n\n"
            f"_Indian Stock Market Research Platform_"
        )
        self.send_telegram_alert(msg)
