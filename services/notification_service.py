import logging
import requests
import smtplib
from collections.abc import Sequence
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import AppConfig
from services.crawl_service import CrawlService
from database.repositories.notification_channel_repository import NotificationChannelRepository

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, crawl_service: CrawlService):
        self.crawl_service = crawl_service
        self.config = AppConfig()
        self.enabled = self.crawl_service.get_setting("notification_enabled", "true") == "true"

    @classmethod
    def from_session(cls, session):
        crawl_service = CrawlService(session)
        return cls(crawl_service)

    def _get_setting(self, key: str, default: str = ""):
        return self.crawl_service.get_setting(key, default)

    def send_slack_notification(self, message: str):
        if not self.enabled:
            return
        webhook_url = self._get_setting("slack_webhook_url", "")
        if not webhook_url:
            logger.info("Slack webhook URL not configured.")
            return
        payload = {"text": message}
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("Slack notification sent.")
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")

    def send_teams_notification(self, message: str):
        if not self.enabled:
            return
        webhook_url = self._get_setting("teams_webhook_url", "")
        if not webhook_url:
            logger.info("Teams webhook URL not configured.")
            return
        payload = {"text": message}
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("Teams notification sent.")
        except Exception as e:
            logger.error(f"Failed to send Teams notification: {e}")

    def send_email_notification(self, subject: str, body: str, to_email: str):
        if not self.enabled:
            return
        smtp_server = self._get_setting("email_smtp_server", "")
        smtp_port = int(self._get_setting("email_smtp_port", "587"))
        smtp_user = self._get_setting("email_smtp_user", "")
        smtp_password = self._get_setting("email_smtp_password", "")
        if not all([smtp_server, smtp_user, smtp_password]):
            logger.warning("Email SMTP configuration incomplete.")
            return
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, to_email, msg.as_string())
            server.quit()
            logger.info(f"Email notification sent to {to_email}.")
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")

    def get_active_channels(self, user_id: str):
        repo = NotificationChannelRepository(self.crawl_service.session)
        return repo.get_active_by_user(user_id)

    def send_line_notification(self, message: str):
        if not self.enabled:
            return
        line_token = self._get_setting("line_token", "")
        if not line_token:
            logger.info("LINE token not configured.")
            return
        headers = {'Authorization': f'Bearer {line_token}'}
        try:
            response = requests.post('https://notify-api.line.me/api/notify', headers=headers, data={'message': message}, timeout=10)
            response.raise_for_status()
            logger.info("LINE notification sent.")
        except Exception as e:
            logger.error(f"Failed to send LINE notification: {e}")

    def notify_url_failures(self, failures: List):
        if not failures:
            return

        subject = "【警告】入札情報収集URLの失効検知"
        message = f"以下の自治体URLへのアクセスに失敗しました。確認してください:\n\n"
        for name, url in failures:
            message += f"・{name}: {url}\n"
        
        message += "\n※本メールはシステムによる自動送信です。"

        self.send_slack_notification(f"🚨 *{subject}*\n{message}")
        self.send_line_notification(f"🚨 {subject}\n{message}")
        admin_email = self._get_setting("admin_email", "")
        if admin_email:
            self.send_email_notification(subject, message, admin_email)