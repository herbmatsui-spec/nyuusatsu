"""
app_admin.py — 管理画面

組織・ユーザー・ロールの管理を行う。
"""
import streamlit as st

from database.engine import get_session
from services.auth_service import AuthService
from database.models.organization import Organization
from database.models.user import User
from database.models.role import Role
from database.models.crawl_priority import CrawlPriority
from database.models.agency_inventory import AgencyInventory
from database.models.qa_review import QAReview, QAStatusEnum
from database.models import SystemSetting
from config import AppConfig
from database.models.quality_threshold import QualityThreshold


def render():
    st.set_page_config(page_title="管理画面", page_icon="🛠", layout="wide")
    st.title("🛠 システム管理")
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(["組織", "ユーザー", "ロール", "優先度マトリクス", "発注機関インベントリ", "人手チェック", "品質しきい値", "システム設定"])

    with get_session() as session:
        auth = AuthService(session)

        with tab1:
            st.subheader("組織")
            with st.form("add_org"):
                name = st.text_input("組織名")
                code = st.text_input("コード")
                if st.form_submit_button("追加") and name:
                    org = Organization(name=name, code=code)
                    session.add(org)
                    session.commit()
                    st.rerun()
            for org in session.query(Organization).all():
                st.write(f"- {org.name} ({org.code})")

        with tab2:
            st.subheader("ユーザー")
            with st.form("add_user"):
                u_name = st.text_input("ユーザー名")
                u_pass = st.text_input("パスワード", type="password")
                u_email = st.text_input("メール")
                orgs = session.query(Organization).all()
                u_org = st.selectbox("組織", orgs, format_func=lambda o: o.name)
                if st.form_submit_button("追加") and u_name:
                    auth.create_user(u_name, u_pass, org_id=u_org.id if u_org else None, email=u_email)
                    session.commit()
                    st.rerun()
            for user in session.query(User).all():
                st.write(f"- {user.username} ({user.email})")

        with tab3:
            st.subheader("ロール")
            with st.form("add_role"):
                r_name = st.text_input("ロール名")
                r_perms = st.text_area("権限 (JSON)", value='["bid:read"]')
                if st.form_submit_button("追加") and r_name:
                    role = Role(name=r_name, permissions_json=r_perms)
                    session.add(role)
                    session.commit()
                    st.rerun()
            for role in session.query(Role).all():
                st.write(f"- {role.name}: {role.permissions_json}")
        
        with tab4:
            st.subheader("優先度マトリクス")
            priorities = session.query(CrawlPriority).all()
            if priorities:
                import pandas as pd
                data = [{
                    "都道府県コード": p.prefecture_code,
                    "都道府県名": p.prefecture_name,
                    "機関数": p.agency_count,
                    "業種一致度": p.target_industry_match,
                    "スコア": p.score,
                    "状態": p.status.value if hasattr(p.status, 'value') else p.status
                } for p in priorities]
                df = pd.DataFrame(data)
                st.dataframe(df)
            else:
                st.info("優先度データがありません。スクリプトを実行してください。")
        
        with tab5:
            st.subheader("発注機関インベントリ")
            inv_list = session.query(AgencyInventory).filter_by(is_crawled=False).limit(100).all()
            if inv_list:
                import pandas as pd
                data = [{
                    "ID": inv.id,
                    "機関名": inv.agency_name,
                    "都道府県コード": inv.prefecture_code,
                    "市区町村": inv.municipality,
                    "入札ページ": inv.bid_page_url,
                    "状態": "未クロール" if not inv.is_crawled else "クロール済"
                } for inv in inv_list]
                df = pd.DataFrame(data)
                st.dataframe(df)
                if st.button("未クロール機関を全てクロール開始"):
                    st.write("※ クロールはバックエンドジョブで実行されます (実装未定)")
            else:
                st.info("全ての機関がクロール済みです。")
        # 人手チェック (QA) タブ
        with tab6:
            st.subheader("人手チェック (QA)")
            pending = session.query(QAReview).filter(QAReview.status == QAStatusEnum.PENDING).limit(20).all()
            if pending:
                import pandas as pd
                df = pd.DataFrame([
                    {
                        "レビューID": r.id,
                        "入札ID": r.bid_id,
                        "ステータス": r.status.value if hasattr(r.status, 'value') else r.status,
                        "作成日時": r.created_at,
                    }
                    for r in pending
                ])
                st.dataframe(df)
                with st.form("qa_action"):
                    rev_id = st.number_input("レビューID", min_value=1, step=1)
                    action = st.selectbox("アクション", ["承認", "却下"])
                    notes = st.text_area("メモ / 修正内容 (JSON)", height=150)
                    if st.form_submit_button("実行"):
                        if action == "承認":
                            import json
                            corrected = {}
                            if notes:
                                try:
                                    corrected = json.loads(notes)
                                except Exception as e:
                                    st.error(f"JSON パースエラー: {e}")
                                    st.stop()
                            from services.qa_fix_pipeline import apply_fix
                            try:
                                apply_fix(session, rev_id, corrected)
                                st.success(f"レビュー {rev_id} を承認し更新しました")
                            except Exception as e:
                                st.error(f"エラー: {e}")
                        else:
                            from services.qa_fix_pipeline import reject
                            try:
                                reject(session, rev_id, notes or "理由未指定")
                                st.success(f"レビュー {rev_id} を却下しました")
                            except Exception as e:
                                st.error(f"エラー: {e}")
            else:
                st.info("保留中の QA レビューはありません")
        # 品質しきい値設定タブ
        with tab7:
            st.subheader("品質しきい値設定")
            thresholds = session.query(QualityThreshold).all()
            if thresholds:
                import pandas as pd
                df = pd.DataFrame([{
                    "ID": t.id,
                    "メトリクス": t.metric_name,
                    "警告しきい値": t.warn_at,
                    "アラートしきい値": t.alert_at,
                } for t in thresholds])
                st.dataframe(df)
            else:
                st.info("しきい値は未設定です。")
            with st.form("threshold_form"):
                metric = st.text_input("メトリクス名 (既存は上書き)")
                warn_val = st.number_input("警告しきい値", step=0.1)
                alert_val = st.number_input("アラートしきい値", step=0.1)
                if st.form_submit_button("保存"):
                    existing = session.query(QualityThreshold).filter_by(metric_name=metric).first()
                    if existing:
                        existing.warn_at = warn_val
                        existing.alert_at = alert_val
                    else:
                        new_th = QualityThreshold(metric_name=metric, warn_at=warn_val, alert_at=alert_val)
                        session.add(new_th)
                    session.commit()
                    st.success(f"しきい値を保存しました: {metric}")
                    st.rerun()
        # システム設定 UI
        with tab8:
            st.subheader("システム設定")
            # キューアラート閾値設定
            setting = session.query(SystemSetting).filter(SystemSetting.key == "queue_alert_threshold").first()
            current_val = int(setting.value) if setting and setting.value.isdigit() else 100
            new_val = st.number_input("キューアラート閾値", min_value=1, value=current_val, step=1)
            if st.button("保存"):
                if setting:
                    setting.value = str(new_val)
                else:
                    setting = SystemSetting(key="queue_alert_threshold", value=str(new_val))
                    session.add(setting)
                session.commit()
                st.success(f"キューアラート閾値を {new_val} に更新しました")
                st.rerun()
        # 追加アラート設定 UI
        with st.expander("システムヘルスアラート設定"):
            st.subheader("ヘルスコンポーネント通知設定")
            # 現在の設定取得
            alert_redis = session.query(SystemSetting).filter(SystemSetting.key == "alert_redis").first()
            alert_db = session.query(SystemSetting).filter(SystemSetting.key == "alert_db").first()
            alert_scheduler = session.query(SystemSetting).filter(SystemSetting.key == "alert_scheduler").first()
            redis_enabled = alert_redis.value.lower() == "true" if alert_redis else False
            db_enabled = alert_db.value.lower() == "true" if alert_db else False
            scheduler_enabled = alert_scheduler.value.lower() == "true" if alert_scheduler else False
            with st.form("health_alert_form"):
                redis_check = st.checkbox("Redis アラート有効化", value=redis_enabled)
                db_check = st.checkbox("DB アラート有効化", value=db_enabled)
                scheduler_check = st.checkbox("Scheduler アラート有効化", value=scheduler_enabled)
                if st.form_submit_button("保存"):
                    for key, val in [("alert_redis", redis_check), ("alert_db", db_check), ("alert_scheduler", scheduler_check)]:
                        setting = session.query(SystemSetting).filter(SystemSetting.key == key).first()
                        if setting:
                            setting.value = str(val)
                        else:
                            setting = SystemSetting(key=key, value=str(val))
                            session.add(setting)
                    session.commit()
                    st.success("ヘルスアラート設定を更新しました")
                    st.rerun()
