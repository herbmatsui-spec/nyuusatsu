import unittest
from datetime import date, datetime
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.models import Base, Bid
from services import mobile_ui_service as service


class MobileServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine)
        self.patch = patch.object(service, "get_session", self.sessions)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.engine.dispose)
        with self.sessions() as session:
            for index in range(25):
                session.add(Bid(
                    id=index + 1, filename="橋梁 補修", organization_name="国土交通省",
                    prefecture_code="13" if index % 2 else "27",
                    announcement_date=datetime(2026, 8, 31, 23, 59),
                    analyzed_at=datetime.now(), current_status="未確認",
                    created_at=datetime.now(), updated_at=datetime.now(),
                ))
            session.commit()
        self.criteria = {"keyword": "橋梁 補修", "organization": "国土", "prefectures": [13, 27], "start": date(2026, 8, 1), "end": date(2026, 8, 31)}

    def test_saved_search_ownership_and_persistence(self):
        from database.models import User
        from services.auth_service import AuthService

        with self.sessions() as session:
            for username in ("alice", "bob"):
                session.add(User(username=username, password_hash=AuthService._hash_password("pass"), is_active=True, created_at=datetime.now()))
            session.commit()
        alice = service.login("alice", "pass")
        bob = service.login("bob", "pass")
        self.assertIsNone(service.login("alice", "wrong"))
        saved_id = service.save_search(alice, "橋梁", self.criteria)
        self.assertEqual(service.saved_searches(alice)[0]["name"], "橋梁")
        self.assertEqual(service.saved_searches(bob), [])
        with self.assertRaises(PermissionError):
            service.delete_search(bob, saved_id)
        with self.assertRaises(PermissionError):
            service.save_search(bob, "変更", self.criteria, saved_id)
        service.save_search(alice, "更新", self.criteria, saved_id)
        self.assertEqual(service.saved_searches(alice)[0]["name"], "更新")
        service.delete_search(alice, saved_id)
        self.assertEqual(service.saved_searches(alice), [])
        service.get_session_manager().logout(alice)
        with self.assertRaises(PermissionError):
            service.saved_searches(alice)

    def test_pagination_offset_merge(self):
        page1 = service.search(self.criteria)
        page2 = service.search(self.criteria, offset=page1["offset"] + len(page1["results"]))
        self.assertEqual(len(page1["results"]), 20)
        self.assertEqual(len(page2["results"]), 5)
        ids1 = {row["id"] for row in page1["results"]}
        ids2 = {row["id"] for row in page2["results"]}
        self.assertFalse(ids1 & ids2)
        self.assertEqual(len(ids1 | ids2), 25)
        self.criteria["keyword"] = "変更後"
        changed = service.search(self.criteria)
        self.assertEqual(changed["offset"], 0)

    def test_account_notifications_and_sync(self):
        from database.models import Agency, User
        from services.auth_service import AuthService

        with self.sessions() as session:
            session.add(User(username="carol", password_hash=AuthService._hash_password("pass"), is_active=True, created_at=datetime.now()))
            session.add(Agency(id=1, name="テスト機関", created_at=datetime.now(), updated_at=datetime.now()))
            session.commit()
        sid = service.login("carol", "pass")
        summary = service.account_summary(sid)
        self.assertEqual(summary["username"], "carol")
        self.assertEqual(summary["plan_code"], "free")
        self.assertIn("次回請求日", summary["next_billing_note"])
        self.assertEqual(service.notification_channels(sid), [])
        updated = service.set_notification_channel(sid, "email", True, "carol@example.com")
        self.assertTrue(updated["is_active"])
        with self.assertRaises(ValueError):
            service.set_notification_channel(sid, "email", True, "invalid")
        with self.assertRaises(ValueError):
            service.set_notification_channel(sid, "fax", True)
        service.set_notification_channel(sid, "line", True)
        types = {c["channel_type"]: c["is_active"] for c in service.notification_channels(sid)}
        self.assertEqual(types, {"email": True, "line": True})
        job_id = service.enqueue_latest_refresh(sid)
        self.assertEqual(service.job_status(job_id)["status"], "pending")
        with self.assertRaises(LookupError):
            with self.sessions() as session:
                session.query(Agency).delete()
                session.commit()
                service.enqueue_latest_refresh(sid)

    def test_filters_and_inclusive_end_date(self):
        page = service.search(self.criteria)
        self.assertEqual(page["total"], 25)
        self.assertEqual(len(page["results"]), 20)
        self.assertEqual(page["results"][0]["id"], 25)
        self.criteria["prefectures"] = [13]
        self.assertEqual(service.search(self.criteria)["total"], 12)
        self.criteria["keyword"] = "存在しない"
        self.assertEqual(service.search(self.criteria)["total"], 0)

    def test_detail_and_missing_record(self):
        self.assertEqual(service.detail(1)["filename"], "橋梁 補修")
        self.assertIsNone(service.detail(1000))

    def test_invalid_dates(self):
        self.criteria["start"] = date(2026, 9, 1)
        with self.assertRaises(ValueError):
            service.search(self.criteria)


if __name__ == "__main__":
    unittest.main()
