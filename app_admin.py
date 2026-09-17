"""
app_admin.py — 管理画面

組織・ユーザー・ロールの管理を行う。
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from database.engine import get_session
from services.auth_service import AuthService
from database.models.organization import Organization
from database.models.user import User
from database.models.role import Role
from database.models.crawl_priority import CrawlPriority
from database.models.agency_inventory import AgencyInventory
from database.models.qa_review import QAReview, QAStatusEnum
from database.models import SystemSetting
from config_dir import AppConfig
from database.models.quality_threshold import QualityThreshold
from database.models import BackfillJob, BackfillJobStatus, BackfillJobLog, Agency, AgencyCategory
from database.models.quality_alert import QualityAlert
from services.backfill_service import BackfillService
from services.quality_alert_service import QualityAlertService
from services.model_tuning import render_model_tuning


def render():
    st.set_page_config(page_title="管理画面", page_icon="🛠", layout="wide")
    st.title("🛠 システム管理")
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs(["組織", "ユーザー", "ロール", "優先度マトリクス", "発注機関インベントリ", "人手チェック", "品質しきい値", "システム設定", "バックフィル", "品質アラート履歴"])

    with get_session() as session:
        auth = AuthService(session)

        with st.expander("予測モデルチューニング"):
            render_model_tuning(session)

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

        with tab6:
            st.subheader("人手チェック (QA)")
            pending = session.query(QAReview).filter(QAReview.status == QAStatusEnum.PENDING).limit(20).all()
            if pending:
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

        with tab7:
            st.subheader("品質しきい値設定")
            thresholds = session.query(QualityThreshold).all()
            if thresholds:
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

        with tab8:
            st.subheader("システム設定")
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
            with st.expander("システムヘルスアラート設定"):
                st.subheader("ヘルスコンポーネント通知設定")
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

        with tab9:
            st.subheader("バックフィル (過去データ遡及取得)")
            service = BackfillService()

            subtab1, subtab2, subtab3 = st.tabs(["ジョブ一覧", "新規ジョブ作成", "統計・レポート"])

            with subtab1:
                # フィルタ
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    status_filter = st.selectbox("ステータス", ["全て"] + [s.value for s in BackfillJobStatus])
                with col2:
                    agency_filter = st.selectbox(
                        "機関",
                        ["全て"] + [f"{a.name} (id={a.id})" for a in session.query(Agency).all()]
                    )
                with col3:
                    date_from = st.date_input("作成日 (開始)", value=datetime.utcnow().date() - timedelta(days=30))
                with col4:
                    date_to = st.date_input("作成日 (終了)", value=datetime.utcnow().date())

                # クエリ構築
                query = session.query(BackfillJob)
                if status_filter != "全て":
                    query = query.filter(BackfillJob.status == BackfillJobStatus(status_filter))
                if agency_filter != "全て":
                    agency_id = int(agency_filter.split("id=")[1].split(")")[0])
                    query = query.filter(BackfillJob.agency_id == agency_id)
                query = query.filter(
                    BackfillJob.created_at >= date_from,
                    BackfillJob.created_at <= date_to + timedelta(days=1)
                )

                jobs = query.order_by(BackfillJob.created_at.desc()).limit(100).all()

                if jobs:
                    # 機関名を取得
                    agency_ids = [j.agency_id for j in jobs]
                    agencies = {a.id: a.name for a in session.query(Agency).filter(Agency.id.in_(agency_ids)).all()}

                    data = [{
                        "ジョブID": j.id,
                        "機関": agencies.get(j.agency_id, f"ID:{j.agency_id}"),
                        "期間": f"{j.start_date} 〜 {j.end_date}",
                        "ステータス": j.status.value,
                        "取得件数": j.fetched_count,
                        "新規": j.new_count,
                        "更新": j.updated_count,
                        "エラー": j.error_count,
                        "リトライ": j.retry_count,
                        "開始": j.started_at.strftime("%Y-%m-%d %H:%M") if j.started_at else "-",
                        "完了": j.finished_at.strftime("%Y-%m-%d %H:%M") if j.finished_at else "-",
                        "エラー詳細": j.error_message or "-",
                    } for j in jobs]
                    df = pd.DataFrame(data)
                    st.dataframe(df, use_container_width=True)

                    # アクション
                    st.divider()
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        selected_job_id = st.number_input("対象ジョブID", min_value=1, step=1, key="action_job_id")
                    with col_b:
                        if st.button("再実行", type="secondary"):
                            if selected_job_id:
                                try:
                                    service.retry_job(selected_job_id)
                                    st.success(f"ジョブ {selected_job_id} を再実行キューに追加しました")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"再実行失敗: {e}")
                    with col_c:
                        if st.button("キャンセル", type="secondary"):
                            if selected_job_id:
                                try:
                                    service.cancel_job(selected_job_id)
                                    st.success(f"ジョブ {selected_job_id} をキャンセルしました")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"キャンセル失敗: {e}")

                    # 詳細表示
                    if st.checkbox("ジョブ詳細表示"):
                        detail_job = st.number_input("詳細ジョブID", min_value=1, step=1, key="detail_job_id")
                        if detail_job_id := detail_job:
                            job = session.query(BackfillJob).get(detail_job_id)
                            if job:
                                st.json({
                                    "id": job.id,
                                    "agency_id": job.agency_id,
                                    "start_date": str(job.start_date),
                                    "end_date": str(job.end_date),
                                    "status": job.status.value,
                                    "fetched_count": job.fetched_count,
                                    "new_count": job.new_count,
                                    "updated_count": job.updated_count,
                                    "error_count": job.error_count,
                                    "error_message": job.error_message,
                                    "retry_count": job.retry_count,
                                    "started_at": str(job.started_at),
                                    "finished_at": str(job.finished_at),
                                    "created_at": str(job.created_at),
                                })
                                # ログ表示
                                logs = session.query(BackfillJobLog).filter(
                                    BackfillJobLog.job_id == detail_job_id
                                ).order_by(BackfillJobLog.created_at).all()
                                if logs:
                                    st.write("**実行ログ**")
                                    log_df = pd.DataFrame([{
                                        "ステップ": l.step,
                                        "メッセージ": l.message,
                                        "レベル": l.level,
                                        "日時": l.created_at,
                                    } for l in logs])
                                    st.dataframe(log_df)
                            else:
                                st.warning("ジョブが見つかりません")
                else:
                    st.info("条件に一致するジョブがありません")

            with subtab2:
                st.write("新規バックフィルジョブを作成します")

                col1, col2 = st.columns(2)
                with col1:
                    agency = st.selectbox(
                        "対象機関",
                        session.query(Agency).all(),
                        format_func=lambda a: f"{a.name} (id={a.id}, type={a.type})"
                    )
                    years = st.number_input("遡及年数", min_value=1, max_value=10, value=2)
                with col2:
                    custom_start = st.date_input("開始日 (指定時は年数無視)", value=None)
                    custom_end = st.date_input("終了日 (指定時は年数無視)", value=None)

                if st.button("ジョブ作成", type="primary"):
                    try:
                        start = custom_start if custom_start else None
                        end = custom_end if custom_end else None
                        job = service.create_job(
                            agency_id=agency.id,
                            years=years,
                            start_date=start,
                            end_date=end,
                        )
                        if job.status == BackfillJobStatus.PENDING:
                            st.success(f"ジョブ作成成功: ID={job.id}, 機関={agency.name}")
                        else:
                            st.warning(f"既存ジョブが存在します: ID={job.id}, ステータス={job.status.value}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"ジョブ作成失敗: {e}")

            with subtab3:
                st.write("バックフィル統計・レポート")

                # 全体統計
                total_jobs = session.query(BackfillJob).count()
                pending_jobs = session.query(BackfillJob).filter(BackfillJob.status == BackfillJobStatus.PENDING).count()
                running_jobs = session.query(BackfillJob).filter(BackfillJob.status == BackfillJobStatus.RUNNING).count()
                done_jobs = session.query(BackfillJob).filter(BackfillJob.status == BackfillJobStatus.DONE).count()
                failed_jobs = session.query(BackfillJob).filter(BackfillJob.status == BackfillJobStatus.FAILED).count()

                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("総ジョブ数", total_jobs)
                col2.metric("待機中", pending_jobs)
                col3.metric("実行中", running_jobs)
                col4.metric("完了", done_jobs)
                col5.metric("失敗", failed_jobs)

                st.divider()

                # 品質レポート生成
                if st.button("品質レポート生成 (JSON)", type="secondary"):
                    from services.backfill_dedup import BackfillDedupService
                    dedup = BackfillDedupService()
                    report = dedup.generate_quality_report()
                    st.json(report)

                # 個別ジョブレポート
                st.subheader("ジョブ別レポート")
                report_job_id = st.number_input("ジョブID", min_value=1, step=1, key="report_job_id")
                if st.button("レポート生成") and report_job_id:
                    from services.backfill_dedup import BackfillDedupService
                    dedup = BackfillDedupService()
                    report = dedup.generate_quality_report(report_job_id)
                    st.json(report)

                # 整合性チェック
                st.divider()
                if st.button("データ整合性チェック実行"):
                    from services.backfill_dedup import BackfillDedupService
                    dedup = BackfillDedupService()
                    result = dedup.check_integrity()
                    st.json(result)

                # 重複修正
                if st.button("重複自動修正 (DRY-RUN)"):
                    from services.backfill_dedup import BackfillDedupService
                    dedup = BackfillDedupService()
                    result = dedup.merge_duplicates(dry_run=True)
                    st.write(f"DRY-RUN 結果: {result}")

                if st.button("重複自動修正 (実行)", type="primary"):
                    from services.backfill_dedup import BackfillDedupService
                    dedup = BackfillDedupService()
                    result = dedup.merge_duplicates(dry_run=False)
                    st.success(f"修正完了: {result}")

        # 品質アラート履歴タブ
        with tab10:
            st.subheader("品質アラート履歴")
            alert_service = QualityAlertService(session)

            # フィルタ
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                level_filter = st.selectbox("レベル", ["全て", "warn", "alert"])
            with col2:
                metric_filter = st.selectbox(
                    "メトリクス",
                    ["全て"] + [row[0] for row in session.query(QualityAlert.metric).distinct().all()]
                )
            with col3:
                date_from = st.date_input("期間 (開始)", value=datetime.utcnow().date() - timedelta(days=30))
            with col4:
                date_to = st.date_input("期間 (終了)", value=datetime.utcnow().date())

            limit = st.slider("表示件数", 10, 200, 50)

            query_level = None if level_filter == "全て" else level_filter
            query_metric = None if metric_filter == "全て" else metric_filter

            alerts = alert_service.get_recent_alerts(
                limit=limit,
                level=query_level,
                metric=query_metric,
                start_date=datetime.combine(date_from, datetime.min.time()),
                end_date=datetime.combine(date_to, datetime.max.time()),
            )

            if alerts:
                df = pd.DataFrame([{
                    "日時": a.sent_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "メトリクス": a.metric,
                    "レベル": "⚠️ 警告" if a.level == "warn" else "🔴 アラート",
                    "値": a.value,
                    "しきい値": a.threshold,
                } for a in alerts])
                st.dataframe(df, use_container_width=True)

                # 詳細モーダル
                st.divider()
                st.subheader("詳細表示")
                selected_id = st.number_input("アラートIDを選択", min_value=1, step=1)
                if st.button("詳細表示"):
                    alert = session.query(QualityAlert).get(selected_id)
                    if alert:
                        st.json({
                            "ID": alert.id,
                            "メトリクス": alert.metric,
                            "レベル": alert.level,
                            "実測値": alert.value,
                            "しきい値": alert.threshold,
                            "通知日時": alert.sent_at.strftime("%Y-%m-%d %H:%M:%S"),
                        })
                    else:
                        st.warning("指定されたアラートが見つかりません")
            else:
                st.info("条件に一致するアラートがありません")