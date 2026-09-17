import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[2] / "app_mobile.py"


class MobileNavigationTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch

        self.search_patch = patch("services.mobile_ui_service.search", return_value={"results": [], "total": 0, "offset": 0})
        self.search = self.search_patch.start()
        self.addCleanup(self.search_patch.stop)

    def test_results_and_details(self):
        from unittest.mock import patch

        self.search.return_value = {"results": [{"id": 1, "filename": "橋梁補修", "prefecture_code": "13"}], "total": 1, "offset": 0}
        app = AppTest.from_file(str(APP)).run()
        app.button[0].click().run()
        with patch("services.mobile_ui_service.detail", return_value={"id": 1, "filename": "橋梁補修"}):
            app.button(key="detail_1").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.expander[0].label, "案件の全情報")

    def test_offline_fallback_cache(self):
        self.search.return_value = {"results": [{"id": 1, "filename": "橋梁補修", "prefecture_code": "13"}], "total": 1, "offset": 0}
        app = AppTest.from_file(str(APP)).run()
        app.text_input(key="mobile_keyword").set_value("橋梁").run()
        app.button[0].click().run()
        self.assertTrue(any("該当 1 件" in c.value for c in app.caption))
        self.search.side_effect = RuntimeError("connection lost")
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("古いデータ" in w.value for w in app.warning))
        self.assertTrue(any(b.value is not None and "橋梁補修" in str(b.value) for b in app.markdown))
        app.text_input(key="mobile_keyword").set_value("別語").run()
        app.button[0].click().run()
        self.assertTrue(any("取得できません" in e.value for e in app.error))

    def test_empty_results_reset(self):
        app = AppTest.from_file(str(APP)).run()
        app.text_input(key="mobile_keyword").set_value("なし").run()
        app.button[0].click().run()
        self.assertEqual(app.info[0].value, "該当する案件はありません")
        app.button[1].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.text_input(key="mobile_keyword").value, "")

    def test_load_more_pagination(self):
        self.search.return_value = {"results": [{"id": i, "filename": f"案件{i}", "prefecture_code": "13"} for i in range(1, 21)], "total": 25, "offset": 0}
        app = AppTest.from_file(str(APP)).run()
        app.text_input(key="mobile_keyword").set_value("橋梁").run()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        labels = [b.label for b in app.button]
        self.assertIn("もっと見る", labels)
        self.search.return_value = {"results": [{"id": i, "filename": f"案件{i}", "prefecture_code": "13"} for i in range(21, 26)], "total": 25, "offset": 20}
        app.button[1].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["mobile_results"]["total"], 25)
        self.assertEqual(len(app.session_state["mobile_results"]["results"]), 25)
        self.search.return_value = {"results": [], "total": 0, "offset": 0}
        app.text_input(key="mobile_keyword").set_value("変更").run()
        app.button[0].click().run()
        self.assertEqual(app.info[0].value, "該当する案件はありません")

    def test_navigation_and_state(self):
        app = AppTest.from_file(str(APP)).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.current_tab, "検索")
        for tab in ("マイ検索", "お知らせ", "設定", "検索"):
            app.radio(key="current_tab").set_value(tab).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.subheader[0].value, tab)
            app.run()
            self.assertEqual(app.session_state.current_tab, tab)

    def test_form_values_survive_navigation(self):
        app = AppTest.from_file(str(APP)).run()
        app.text_input(key="mobile_keyword").set_value("橋梁").run()
        app.multiselect(key="mobile_prefectures").set_value([13, 27]).run()
        app.radio(key="current_tab").set_value("設定").run()
        app.radio(key="current_tab").set_value("検索").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.text_input(key="mobile_keyword").value, "橋梁")
        self.assertEqual(app.multiselect(key="mobile_prefectures").value, [13, 27])
        self.assertTrue(app.selectbox[0].disabled)

    def test_search_submission(self):
        from datetime import date

        app = AppTest.from_file(str(APP)).run()
        app.text_input(key="mobile_keyword").set_value("橋梁 補修")
        app.text_input(key="mobile_organization").set_value("国土交通省")
        app.multiselect(key="mobile_prefectures").set_value([13, 27])
        app.date_input(key="mobile_start").set_value(date(2026, 8, 1))
        app.date_input(key="mobile_end").set_value(date(2026, 8, 31))
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.mobile_submitted, {
            "keyword": "橋梁 補修", "organization": "国土交通省",
            "prefectures": [13, 27], "start": date(2026, 8, 1), "end": date(2026, 8, 31),
        })

    def test_invalid_dates(self):
        from datetime import date

        app = AppTest.from_file(str(APP)).run()
        app.date_input(key="mobile_start").set_value(date(2026, 9, 20)).run()
        app.date_input(key="mobile_end").set_value(date(2026, 9, 1)).run()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertIn("開始日", app.error[0].value)

    def test_external_css_loaded(self):
        css_path = APP.parent / "static" / "css" / "mobile.css"
        self.assertTrue(css_path.exists())
        css = css_path.read_text(encoding="utf-8")
        self.assertIn("48px", css)
        self.assertIn("prefers-color-scheme: dark", css)
        self.assertIn("orientation: landscape", css)
        with patch.object(Path, "read_text", side_effect=OSError):
            app = AppTest.from_file(str(APP)).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("CSS" in w.value for w in app.warning))

        app = AppTest.from_file(str(APP)).run()
        app.radio(key="current_tab").set_value("お知らせ").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("ログイン" in info.value for info in app.info))

        app = AppTest.from_file(str(APP)).run()
        app.radio(key="current_tab").set_value("お知らせ").run()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.current_tab, "設定")


if __name__ == "__main__":
    unittest.main()
