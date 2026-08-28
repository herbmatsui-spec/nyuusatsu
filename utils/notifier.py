import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from typing import Optional

class Notifier:
    """
    Email notification handler for alerting administrators.
    """
    def __init__(self):
        self.smtp_server = os.environ.get("SMTP_SERVER", "")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_user = os.environ.get("SMTP_USER", "")
        self.smtp_password = os.environ.get("SMTP_PASSWORD", "")
        self.admin_email = os.environ.get("ADMIN_EMAIL", "")
        self.from_email = os.environ.get("FROM_EMAIL", "")
        
        self.enabled = all([self.smtp_server, self.smtp_user, self.smtp_password, self.admin_email, self.from_email])
        self.logger = logging.getLogger(__name__)

    def send_notification(self, subject: str, body: str) -> bool:
        if not self.enabled:
            self.logger.warning("Notification not configured. Skipping email.")
            return False
            
        msg = MIMEMultipart()
        msg["From"] = self.from_email
        msg["To"] = self.admin_email
        msg["Subject"] = subject
        
        msg.attach(MIMEText(body, "plain"))
        
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            self.logger.info(f"Notification sent: {subject}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")
            return False

    def notify_new_bids(self, count: int, url: str):
        subject = f"新着案件 {count} 件を検出"
        body = f"""
新着入札案件が検出されました。

検出数: {count} 件
URL: {url}

確認してください。
        """
        self.send_notification(subject, body)

    def notify_critical_error(self, error: str):
        subject = "入札システムエラー通知"
        body = f"""
入札システムで重大なエラーが発生しました。

エラー内容:
{error}

調査をお願いします。
        """
        self.send_notification(subject, body)