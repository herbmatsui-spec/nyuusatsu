"""
分析サービス層
──────────────
BidRepository の集計クエリをラップし、ダッシュボード向けの
高レベルな分析データを提供する。また、長文ドキュメントの
コンテキスト管理とLLM分析を制御する。
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

from database.repositories.bid_repository import BidRepository
from database.models import Bid
from ocr.base import OCRProvider

class TextProcessor:
    """コンテキストウィンドウ制限を解消するためのテキスト処理クラス"""
    
    def __init__(self, chunk_size: int = 8000, overlap: int = 500):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split_text(self, text: str) -> List[str]:
        """テキストをオーバーラップ付きのチャンクに分割"""
        if not text:
            return []
        
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunks.append(text[start:end])
            start += self.chunk_size - self.overlap
        return chunks

    def compress_context(self, chunks: List[str], client: Any, model_name: str) -> str:
        """Map-Reduce方式で重要情報を抽出してコンテキストを圧縮"""
        # 1. 各チャンクから重要箇所（納期、成果物、予算等）を抽出 (Map)
        extracted_parts = []
        for i, chunk in enumerate(chunks):
            prompt = f"以下の文書チャンクから【予算・納期・成果物・参加資格】に関する重要な記述のみを抽出してください。不要な挨拶や形式的な文言は除いてください。\n\n---CHUNK {i}---\n{chunk}"
            try:
                response = client.models.generate_content(model=model_name, contents=prompt)
                extracted_parts.append(response.text)
            except Exception:
                extracted_parts.append(f"Chunk {i} analysis failed")

        # 2. 抽出結果を統合して最終的な要約を作成 (Reduce)
        combined_text = "\n\n".join(extracted_parts)
        final_prompt = f"以下は文書の各箇所から抽出された重要情報です。これらを統合し、矛盾を解消した上で、最終的な要件定義書として整理してください。\n\n{combined_text}"
        
        try:
            response = client.models.generate_content(model=model_name, contents=final_prompt)
            return response.text
        except Exception:
            return combined_text

class AnalysisService:
    """ダッシュボード・分析向けのサービス"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = BidRepository(session)
        self.text_processor = TextProcessor()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def analyze_document_async(self, text: str, client: Any, model_name: str, schema: Any) -> Optional[Dict[str, Any]]:
        """非同期かつリトライ付きでドキュメントを分析"""
        chunks = self.text_processor.split_text(text)
        
        # 長文の場合はコンテキスト圧縮を行う
        if len(chunks) > 1:
            processed_text = self.text_processor.compress_context(chunks, client, model_name)
        else:
            processed_text = text

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=processed_text,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                },
            )
            return response.parsed.model_dump()
        except Exception as e:
            logging.error(f"Analysis error: {e}")
            return None

    # ... (Existing get_overview, etc. keep them as they are)

    # ── Step 9: 全体概要統計 ──────────────────────────────────────────

    def get_overview(self) -> dict:
        """ダッシュボードの KPI カード用 全体概要 を一度に返す。

        Returns
        -------
        {
            "total_bids": int,                 # 総案件数
            "status_distribution": List[dict],  # ステータス分布
            "win_loss": dict,                   # 落札率/失注率
            "monthly_trend": List[dict],        # 月別登録数（直近12ヶ月）
            "top_organizations": List[dict],    # 上位5機関
            "top_industries": List[dict],       # 上位5業種
            "budget_distribution": List[dict],  # 予算規模分布
        }
        """
        return {
            "total_bids": self.get_total_bids(),
            "status_distribution": self.get_status_distribution(),
            "win_loss": self.get_win_loss_stats(),
            "monthly_trend": self.get_monthly_trend(months=12),
            "top_organizations": self.get_top_organizations(top_n=5),
            "top_industries": self.get_top_industries(top_n=5),
            "budget_distribution": self.get_budget_distribution(),
        }

    def get_total_bids(self) -> int:
        """総案件数"""
        return self.repo.count_all()

    # ── Step 10: ステータス分布分析 ────────────────────────────────────

    def get_status_distribution(self) -> List[dict]:
        """ステータス分布を返す（カテゴリ別件数 + 全体比）。

        Returns
        -------
        [{"status": "未確認", "count": 42, "ratio": 50.0}, ...]
        """
        rows = self.repo.count_by_status()
        total = sum(r["count"] for r in rows)
        for r in rows:
            r["ratio"] = round(r["count"] / total * 100, 1) if total > 0 else 0.0
        return rows

    # ── Step 11: 業種別傾向分析 ────────────────────────────────────────

    def get_top_industries(self, top_n: int = 5) -> List[dict]:
        """上位 N 業種を返す。

        Returns
        -------
        [{"industry": "情報通信", "count": 15, "ratio": 30.0}, ...]
        """
        rows = self.repo.count_by_industry()
        total = sum(r["count"] for r in rows)
        for r in rows:
            r["ratio"] = round(r["count"] / total * 100, 1) if total > 0 else 0.0
        return rows[:top_n]

    def get_industry_distribution(self) -> List[dict]:
        """全業種の分布（フィルタなし完全リスト）"""
        rows = self.repo.count_by_industry()
        total = sum(r["count"] for r in rows)
        for r in rows:
            r["ratio"] = round(r["count"] / total * 100, 1) if total > 0 else 0.0
        return rows

    # ── Step 12: 機関別傾向分析 ────────────────────────────────────────

    def get_top_organizations(self, top_n: int = 5) -> List[dict]:
        """上位 N 機関を返す。

        Returns
        -------
        [{"organization": "デジタル庁", "count": 12, "ratio": 24.0}, ...]
        """
        rows = self.repo.count_by_organization()
        total = sum(r["count"] for r in rows)
        for r in rows:
            r["ratio"] = round(r["count"] / total * 100, 1) if total > 0 else 0.0
        return rows[:top_n]

    def get_organization_distribution(self) -> List[dict]:
        """全機関の分布（フィルタなし完全リスト）"""
        rows = self.repo.count_by_organization()
        total = sum(r["count"] for r in rows)
        for r in rows:
            r["ratio"] = round(r["count"] / total * 100, 1) if total > 0 else 0.0
        return rows

    # ── Step 13: 時系列トレンド分析 ────────────────────────────────────

    def get_monthly_trend(self, months: int = 12) -> List[dict]:
        """月別の案件登録数（直近 N ヶ月）。

        Returns
        -------
        [{"month": "2025-01", "count": 8}, ...]  ascending by month
        """
        rows = self.repo.count_by_month()
        # リポジトリは全期間の月別を返すため、末尾 months 件に絞る
        return rows[-months:] if len(rows) > months else rows

    def get_full_timeline(self) -> List[dict]:
        """全期間の月別トレンド（絞り込みなし）"""
        return self.repo.count_by_month()

    # ── Step 14: 予算規模分析 ──────────────────────────────────────────

    def get_budget_distribution(self) -> List[dict]:
        """予算規模の分布（全カテゴリ + 比率付き）。

        Returns
        -------
        [{"budget": "500～1,000万円", "count": 8, "ratio": 16.0}, ...]
        """
        rows = self.repo.count_by_budget_range()
        total = sum(r["count"] for r in rows)
        for r in rows:
            r["ratio"] = round(r["count"] / total * 100, 1) if total > 0 else 0.0
        return rows

    # ── Step 15: 落札率・成功率の詳細分析 ──────────────────────────────

    def get_win_loss_stats(self) -> dict:
        """落札率 / 失注率 の集計。

        Returns
        -------
        {
            "win_count": int,
            "loss_count": int,
            "total_closed": int,
            "win_rate": float,   # 百分率 (0.0–100.0)
            "loss_rate": float,  # 百分率
        }
        """
        stats = self.repo.get_win_loss_stats()
        stats["loss_rate"] = round(100.0 - stats["win_rate"], 1)
        return stats

    def get_status_funnel(self) -> List[dict]:
        """ステータスファネル（応募プロセスの流入→流出分析）。

        未確認 → 検討中 → 応募済 → (落札 / 失注) の各段階の件数と
        前段階からの遷移率を計算する。

        Returns
        -------
        [
            {"status": "未確認",  "count": N, "conversion_from_prev": None},
            {"status": "検討中",  "count": N, "conversion_from_prev": 70.0},
            {"status": "応募済",  "count": N, "conversion_from_prev": 45.0},
            {"status": "落札",    "count": N, "conversion_from_prev": 60.0},
            {"status": "失注",    "count": N, "conversion_from_prev": 40.0},
        ]
        """
        dist = self.repo.count_by_status()
        status_map = {r["status"]: r["count"] for r in dist}

        funnel_order = ["未確認", "検討中", "応募済", "落札", "失注"]
        result: List[dict] = []
        prev_count: Optional[int] = None

        for status in funnel_order:
            count = status_map.get(status, 0)
            entry: dict = {"status": status, "count": count}
            if prev_count is not None and prev_count > 0:
                entry["conversion_from_prev"] = round(count / prev_count * 100, 1)
            else:
                entry["conversion_from_prev"] = None
            result.append(entry)
            # "応募済" の次は 落札+失注 の合計を分母にする
            if status == "応募済":
                prev_count = status_map.get("落札", 0) + status_map.get("失注", 0)
            else:
                prev_count = count

        return result

    # ── Step 25: 落札率時系列分析 ──────────────────────────────────────

    def get_win_rate_trend(self, months: int = 12) -> List[dict]:
        """月別落札率の推移を取得。

        Parameters
        ----------
        months : int
            直近何ヶ月分を返すか（デフォルト 12）。

        Returns
        -------
        List[dict]
            [
                {"month": "2025-04", "total": 5, "win_count": 3, "loss_count": 2, "win_rate": 60.0},
                ...
            ]
        """
        monthly = self.repo.count_win_loss_by_month()
        if months > 0:
            return monthly[-months:]
        return monthly

    # ── Step 16: 期間絞り込み機能 ──────────────────────────────────────

    def get_bids_in_range(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[Bid]:
        """指定期間内の案件一覧を返す。

        Parameters
        ----------
        start_date : datetime | None
            期間の開始日時 (created_at >= start_date)
        end_date : datetime | None
            期間の終了日時 (created_at <= end_date)

        Returns
        -------
        List[Bid] — ORM インスタンスのリスト（created_at 降順）
        """
        return self.repo.list_by_date_range(start_date, end_date)

    def get_bid_detail(self, bid_id: int) -> Optional[dict]:
        """指定された案件の詳細情報を返す。

        Parameters
        ----------
        bid_id : int
            案件ID

        Returns
        -------
        Optional[dict]
            案件詳細情報。存在しない場合はNone。
        """
        import json
        bid = self.repo.get_by_id(bid_id)
        if bid is None:
            return None

        # ステータス履歴のシリアル化
        status_history = []
        for status_record in sorted(bid.statuses, key=lambda s: s.changed_at, reverse=True):
            status_history.append({
                "status": status_record.status,
                "changed_at": status_record.changed_at.strftime("%Y-%m-%d %H:%M") if status_record.changed_at else "不明",
                "changed_by": status_record.changed_by or "不明",
                "memo": status_record.memo or "",
            })

        return {
            "基本情報": {
                "ID": bid.id,
                "案件名 (ファイル名)": bid.filename or "不明",
                "ソースURL": bid.source_url or "不明",
                "登録日": bid.created_at.strftime("%Y-%m-%d %H:%M") if bid.created_at else "不明",
                "解析日": bid.analyzed_at.strftime("%Y-%m-%d %H:%M") if bid.analyzed_at else "未解析",
                "更新日": bid.updated_at.strftime("%Y-%m-%d %H:%M") if bid.updated_at else "不明",
            },
            "予算・応札情報": {
                "予算（原文）": bid.budget or "不明",
                "予算解析結果": json.loads(bid.budget) if bid.budget else None,
                "落札額": f"{bid.actual_bid_amount:,}円" if bid.actual_bid_amount else "不明",
                "落札/失注理由": bid.win_loss_reason or "不明",
            },
            "要件・リスク": {
                "参加資格": json.loads(bid.qualifications) if bid.qualifications else "不明",
                "成果物": json.loads(bid.deliverables) if bid.deliverables else "不明",
                "主要リスク": json.loads(bid.key_risks) if bid.key_risks else "不明",
                "備考": bid.notes or "なし",
            },
            "分類情報": {
                "業種": bid.industry_category or "不明",
                "機関名": bid.organization_name or "不明",
                "ステータス": bid.current_status or "未確認",
            },
            "ステータス履歴": status_history,
        }

    def get_filtered_overview(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> dict:
        """指定期間に絞り込んだ全体概要。

        期間内の案件に対して KPI カード相当の統計を返す。
        get_overview() と同様の構造だが、集計対象が期間内に限定される。

        Returns
        -------
        get_overview() と同じキー構造の dict
        """
        bids = self.repo.list_by_date_range(start_date, end_date)
        total = len(bids)

        if total == 0:
            return {
                "total_bids": 0,
                "status_distribution": [],
                "win_loss": {
                    "win_count": 0, "loss_count": 0,
                    "total_closed": 0, "win_rate": 0.0, "loss_rate": 0.0,
                },
                "monthly_trend": [],
                "top_organizations": [],
                "top_industries": [],
                "budget_distribution": [],
            }

        # ── ステータス分布（手動集計） ──
        status_counter: Dict[str, int] = {}
        for bid in bids:
            st = bid.current_status or "不明"
            status_counter[st] = status_counter.get(st, 0) + 1
        status_distribution = [
            {"status": k, "count": v, "ratio": round(v / total * 100, 1)}
            for k, v in sorted(status_counter.items(), key=lambda x: -x[1])
        ]

        # ── 落札率 ──
        win_count = status_counter.get("落札", 0)
        loss_count = status_counter.get("失注", 0)
        total_closed = win_count + loss_count
        win_rate = round(win_count / total_closed * 100, 1) if total_closed > 0 else 0.0
        loss_rate = round(100.0 - win_rate, 1)

        # ── 月別トレンド ──
        month_counter: Dict[str, int] = {}
        for bid in bids:
            if bid.created_at:
                month_key = bid.created_at.strftime("%Y-%m")
                month_counter[month_key] = month_counter.get(month_key, 0) + 1
        monthly_trend = [
            {"month": k, "count": v}
            for k, v in sorted(month_counter.items())
        ]

        # ── 上位機関 ──
        org_counter: Dict[str, int] = {}
        for bid in bids:
            org = bid.organization_name or "不明"
            org_counter[org] = org_counter.get(org, 0) + 1
        top_organizations = [
            {"organization": k, "count": v, "ratio": round(v / total * 100, 1)}
            for k, v in sorted(org_counter.items(), key=lambda x: -x[1])[:5]
        ]

        # ── 上位業種 ──
        ind_counter: Dict[str, int] = {}
        for bid in bids:
            ind = bid.industry_category or "不明"
            ind_counter[ind] = ind_counter.get(ind, 0) + 1
        top_industries = [
            {"industry": k, "count": v, "ratio": round(v / total * 100, 1)}
            for k, v in sorted(ind_counter.items(), key=lambda x: -x[1])[:5]
        ]

        # ── 予算規模分布 ──
        budget_counter: Dict[str, int] = {}
        for bid in bids:
            budget = bid.budget or "不明"
            budget_counter[budget] = budget_counter.get(budget, 0) + 1
        budget_distribution = [
            {"budget": k, "count": v, "ratio": round(v / total * 100, 1)}
            for k, v in sorted(budget_counter.items(), key=lambda x: -x[1])
        ]

        return {
            "total_bids": total,
            "status_distribution": status_distribution,
            "win_loss": {
                "win_count": win_count,
                "loss_count": loss_count,
                "total_closed": total_closed,
                "win_rate": win_rate,
                "loss_rate": loss_rate,
            },
            "monthly_trend": monthly_trend,
            "top_organizations": top_organizations,
            "top_industries": top_industries,
            "budget_distribution": budget_distribution,
        }

    def get_cross_tabulation(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """業種 × 機関のクロス集計（マトリックス）。

        戻り値:
            {
                "industries": ["IT・通信", "建設", ...],
                "organizations": ["機構A", "省庁B", ...],
                "matrix": [[3, 1, 0], [2, 5, 1], ...],
                "matrix_data": [
                    {"industry": "IT・通信", "organization": "機構A", "count": 3},
                    ...
                ],
            }
        """
        bids = self.repo.list_by_date_range(start_date=start_date, end_date=end_date)

        from collections import defaultdict
        cross: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for bid in bids:
            industry = bid.industry_category.strip() if bid.industry_category and bid.industry_category.strip() else "未分類"
            organization = bid.organization_name.strip() if bid.organization_name and bid.organization_name.strip() else "不明"
            cross[industry][organization] += 1

        industries = sorted(cross.keys())
        organizations_set: set[str] = set()
        for org_map in cross.values():
            organizations_set.update(org_map.keys())
        organizations = sorted(organizations_set)

        matrix: list[list[int]] = []
        matrix_data: list[dict[str, object]] = []
        for industry in industries:
            row: list[int] = []
            for organization in organizations:
                count = cross[industry].get(organization, 0)
                row.append(count)
                matrix_data.append({
                    "industry": industry,
                    "organization": organization,
                    "count": count,
                })
            matrix.append(row)

        return {
            "industries": industries,
            "organizations": organizations,
            "matrix": matrix,
            "matrix_data": matrix_data,
        }

    def get_loss_reason_analysis(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> dict:
        """失注理由の集計（ダッシュボード Step 28 用）

        失注案件の win_loss_reason を理由ごとにカウントし、
        割合と総数を付与した集計結果を返す。

        Parameters
        ----------
        start_date : datetime | None
            期間の開始日 (created_at >= start_date)
        end_date : datetime | None
            期間の終了日 (created_at <= end_date)

        Returns
        -------
        dict
            {
                "items": [{"reason": str, "count": int, "percentage": float}, ...],
                "total": int
            }
        """
        reason_counts = self.repo.count_loss_reasons(start_date, end_date)
        total_loss = sum(r["count"] for r in reason_counts)
        return {
            "items": [
                {
                    **r,
                    "percentage": round(r["count"] / total_loss * 100, 1) if total_loss > 0 else 0.0,
                }
                for r in reason_counts
            ],
            "total": total_loss,
        }

    def get_target_organizations(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        min_bids: int = 3,
    ) -> dict:
        """落札率の低いターゲット機関の特定（ダッシュボード Step 29 用）

        各機関ごとに総応募数・落札数・失注数・落札率を集計し、
        最低応募件数以上の機関のみを落札率昇順で返す。落札率が低い機関ほど
        優先的な営業ターゲットとみなす。

        Parameters
        ----------
        start_date : datetime | None
            期間の開始日
        end_date : datetime | None
            期間の終了日
        min_bids : int
            最低応募件数フィルター（デフォルト 3件）

        Returns
        -------
        dict
            {"items": [{organization, total_bids, wins, losses, win_rate}, ...], "total": int}
        """
        org_data = self.repo.find_target_organizations(start_date, end_date, min_bids)
        return {
            "items": org_data,
            "total": len(org_data),
        }

    def get_custom_kpis(self, kpis: List[str]) -> dict:
        """ユーザーが選択したカスタム KPI を取得

        Parameters
        ----------
        kpis : List[str]
            KPI 名のリスト。サポートされれる名前は以下:
            - "total_bids"
            - "win_rate"
            - "average_bid_amount"

        Returns
        -------
        dict
            {kpi_name: value, ...}
        """
        result: dict = {}
        for kpi in kpis:
            if kpi == "total_bids":
                result[kpi] = self.get_total_bids()
            elif kpi == "win_rate":
                result[kpi] = self.get_win_loss_stats().get("win_rate")
            elif kpi == "average_bid_amount":
                result[kpi] = self.repo.average_bid_amount()
        return result