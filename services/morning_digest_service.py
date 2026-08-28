from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from services.saved_search_service import SavedSearchService
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class MorningDigestService:
    def __init__(self, session):
        self.session = session
        self.saved_search_service = SavedSearchService(session)
        self.notifier = NotificationService.from_session(session)

    def run_morning_digest(self):
        searches = self.saved_search_service.get_for_morning_digest()
        if not searches:
            logger.info("No active saved searches for morning digest.")
            return

        for saved in searches:
            try:
                since = saved.last_notified_at or datetime(1970, 1, 1)
                matched = self.saved_search_service.match_new_bids(saved, since)
                if not matched:
                    continue

                channels = self.notifier.get_active_channels(saved.user_id)
                if not channels:
                    continue

                for ch in channels:
                    self._send_digest(ch, saved, matched)

                self.saved_search_service.mark_notified(saved)
                self.session.commit()
                logger.info("Morning digest sent for search %s (%d matches)", saved.id, len(matched))
            except Exception as exc:
                logger.error("Morning digest failed for search %s: %s", saved.id, exc)

    def _send_digest(self, channel, saved_search, matched: List[dict]):
        lines = [f"【毎朝アラート】{saved_search.name} の新着案件 ({len(matched)}件)"]
        for m in matched:
            lines.append(f"- {m.get('filename')} / {m.get('organization_name')} / {m.get('budget')}")
        body = "\n".join(lines)

        if channel.channel_type == "slack" and channel.webhook_url:
            self.notifier.send_slack_notification(body)
        elif channel.channel_type == "teams" and channel.webhook_url:
            self.notifier.send_teams_notification(body)
        elif channel.channel_type == "email" and channel.email_address:
            self.notifier.send_email_notification(
                subject=f"【毎朝アラート】{saved_search.name}",
                body=body,
                to_email=channel.email_address,
            )
