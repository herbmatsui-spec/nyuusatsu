import hashlib
import json
import logging
import os
import pickle
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional
from uuid import uuid4
from weakref import WeakKeyDictionary

import numpy as np
from scipy.sparse import csr_matrix, issparse
from sqlalchemy.orm import Session

from database.models import Bid
from services.prediction_model_config import get_config
from services.similarity_preprocess import get_clean_specification_text

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CACHE_DIR = str(_PROJECT_ROOT / "data" / "similarity_cache")
_ARTIFACT_VERSION = 2
_SHARED_ARTIFACTS = OrderedDict()
_SHARED_ARTIFACT_LIMIT = 4
_CACHE_LOCK = RLock()
_MEMORY_DATABASE_IDS = WeakKeyDictionary()
_FIELDS = (
    "id", "specification_text_clean", "specification_text", "deliverables",
    "qualifications", "announcement_date", "prefecture_code", "industry_category",
    "filename", "organization_name", "budget_amount", "awarded_company",
)


class TextSimilarityService:
    def __init__(self, session: Session, cache_dir: str | None = None):
        self.session = session
        self.cache_dir = cache_dir or _DEFAULT_CACHE_DIR
        self.vectorizer = None
        self.tfidf_matrix: csr_matrix | None = None
        self.doc_ids: List[int] = []
        self._indices = {}
        self._is_built = False
        self._last_build_time: datetime | None = None
        self._similarity_cache = OrderedDict()
        self._artifact = None

    @property
    def config(self) -> Dict[str, Any]:
        return get_config().get("similarity", {})

    @property
    def tfidf_params(self) -> Dict[str, Any]:
        cfg = get_config().get("tfidf", {})
        params = {
            "max_features": cfg.get("max_features", 5000),
            "analyzer": cfg.get("analyzer", "char_wb"),
            "ngram_range": tuple(cfg.get("ngram_range", [2, 5])),
        }
        stop = cfg.get("stop_words")
        if stop == "japanese":
            from config.japanese_stopwords import JAPANESE_STOP_WORDS
            params["stop_words"] = JAPANESE_STOP_WORDS
        elif isinstance(stop, list):
            params["stop_words"] = stop
        return params

    def _months(self, months):
        value = int(self.config.get("time_window_months", 6)) if months is None else int(months)
        if value < 0:
            raise ValueError("months must be nonnegative (0 means unlimited)")
        return value

    def get_specification_text(self, bid: Bid) -> str:
        clean = getattr(bid, "specification_text_clean", None)
        if clean and clean.strip():
            return clean
        return get_clean_specification_text(
            getattr(bid, "specification_text", None),
            getattr(bid, "deliverables", None),
            getattr(bid, "qualifications", None),
        )

    def _database_identity(self):
        bind = self.session.get_bind(mapper=Bid)
        engine = getattr(bind, "engine", bind)
        url = engine.url
        if url.get_backend_name() == "sqlite" and url.database in (None, "", ":memory:"):
            with _CACHE_LOCK:
                return _MEMORY_DATABASE_IDS.setdefault(engine, uuid4().hex)
        return hashlib.sha256(url.render_as_string(hide_password=False).encode()).hexdigest()

    def _snapshot(self):
        with self.session.no_autoflush:
            rows = self.session.query(*(getattr(Bid, field) for field in _FIELDS)).order_by(Bid.id).all()
        digest = hashlib.sha256()
        for row in rows:
            digest.update(repr(tuple(row)).encode("utf-8"))
            digest.update(b"\n")
        config = json.dumps(
            {"tfidf": self.tfidf_params, "similarity": self.config},
            sort_keys=True, default=str,
        )
        return rows, (self._database_identity(), config, digest.hexdigest())

    def _fetch_bids(self, months: Optional[int] = None):
        months = self._months(months)
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30 * months)
        with self.session.no_autoflush:
            query = self.session.query(Bid).order_by(Bid.id)
            if months:
                query = query.filter(Bid.announcement_date >= cutoff)
            return query.all()

    def _reset(self):
        with _CACHE_LOCK:
            self._similarity_cache.clear()
        self._artifact = None
        self.vectorizer = None
        self.tfidf_matrix = None
        self.doc_ids = []
        self._indices = {}
        self._is_built = False
        self._last_build_time = None
        self._similarity_cache = OrderedDict()

    def _attach(self, artifact):
        self._artifact = artifact
        self.vectorizer = artifact["vectorizer"]
        self.tfidf_matrix = artifact["tfidf_matrix"]
        self.doc_ids = artifact["doc_ids"]
        self._indices = artifact["indices"]
        self._last_build_time = artifact["build_time"]
        self._similarity_cache = artifact["results"]
        self._is_built = bool(self.doc_ids)

    def _publish(self, artifact):
        key = (artifact["fingerprint"], artifact["months"], artifact["max_docs"])
        with _CACHE_LOCK:
            previous = _SHARED_ARTIFACTS.pop(key, None)
            if previous is not None:
                previous["results"].clear()
            _SHARED_ARTIFACTS[key] = artifact
            while len(_SHARED_ARTIFACTS) > _SHARED_ARTIFACT_LIMIT:
                _SHARED_ARTIFACTS.popitem(last=False)
        self._attach(artifact)

    @staticmethod
    def _date(value):
        if value is not None and value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def _build(self, rows, fingerprint, months, max_docs):
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._reset()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = now - timedelta(days=30 * months)
        selected = [row for row in rows if not months or (
            row.announcement_date is not None and self._date(row.announcement_date) >= cutoff
        )]
        texts, records = [], []
        for row in selected:
            text = self.get_specification_text(row)
            if text and len(text) > 10:
                if max_docs is not None and len(texts) >= max_docs:
                    break
                texts.append(text)
                records.append({field: getattr(row, field) for field in _FIELDS[5:]} | {"id": row.id, "deliverables": row.deliverables})
        if not texts:
            return 0
        vectorizer = TfidfVectorizer(**self.tfidf_params)
        try:
            matrix = vectorizer.fit_transform(texts).tocsr()
        except ValueError as exc:
            if "empty vocabulary" not in str(exc):
                raise
            return 0
        doc_ids = [record["id"] for record in records]
        artifact = {
            "version": _ARTIFACT_VERSION,
            "fingerprint": fingerprint,
            "months": months,
            "max_docs": max_docs,
            "vectorizer": vectorizer,
            "tfidf_matrix": matrix,
            "doc_ids": doc_ids,
            "indices": {doc_id: index for index, doc_id in enumerate(doc_ids)},
            "records": records,
            "build_time": now,
            "results": OrderedDict(),
        }
        self._publish(artifact)
        logger.info("Built TF-IDF vectors for %d bids", len(doc_ids))
        return len(doc_ids)

    def build(self, months: Optional[int] = None, max_docs: Optional[int] = None) -> int:
        months = self._months(months)
        if max_docs is not None and max_docs < 0:
            raise ValueError("max_docs must be nonnegative")
        rows, fingerprint = self._snapshot()
        return self._build(rows, fingerprint, months, max_docs)

    @staticmethod
    def _compatible(artifact, fingerprint, months):
        return (
            artifact.get("version") == _ARTIFACT_VERSION
            and artifact.get("fingerprint") == fingerprint
            and (artifact["months"] == 0 or (months > 0 and artifact["months"] >= months))
        )

    def _ensure_built(self, months: Optional[int] = None) -> bool:
        months = self._months(months)
        rows, fingerprint = self._snapshot()
        if self._artifact is not None and self._compatible(self._artifact, fingerprint, months):
            return self._is_built
        self._reset()
        with _CACHE_LOCK:
            for key, artifact in reversed(_SHARED_ARTIFACTS.items()):
                if artifact["max_docs"] is None and self._compatible(artifact, fingerprint, months):
                    _SHARED_ARTIFACTS.move_to_end(key)
                    self._attach(artifact)
                    return self._is_built
        if self._load_vectors(None, fingerprint, months):
            return True
        return self._build(rows, fingerprint, months, None) > 0

    def _get_vector(self, doc_index: int) -> csr_matrix:
        return self.tfidf_matrix.getrow(doc_index)

    def _doc_id_to_index(self, doc_id: int) -> Optional[int]:
        return self._indices.get(doc_id)

    def _query_vector(self, doc_id):
        index = self._doc_id_to_index(doc_id)
        if index is not None:
            return self._get_vector(index)
        with self.session.no_autoflush:
            bid = self.session.query(*(getattr(Bid, field) for field in _FIELDS)).filter(Bid.id == doc_id).first()
        if bid is None:
            return None
        text = self.get_specification_text(bid)
        return self.vectorizer.transform([text]) if text else None

    def get_similarity(self, doc_id1: int, doc_id2: int) -> float:
        if not self._ensure_built():
            return 0.0
        vec1, vec2 = self._query_vector(doc_id1), self._query_vector(doc_id2)
        if vec1 is None or vec2 is None:
            return 0.0
        return round(float(np.clip(vec1.multiply(vec2).sum(), 0.0, 1.0)), 4)

    def _candidate_indices(self, doc_id, months, prefecture_code, industry_category):
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30 * months)
        return tuple(
            index for index, record in enumerate(self._artifact["records"])
            if record["id"] != doc_id
            and (not months or (record["announcement_date"] is not None
                 and self._date(record["announcement_date"]) >= cutoff))
            and (not prefecture_code or record["prefecture_code"] == prefecture_code)
            and (not industry_category or record["industry_category"] == industry_category)
        )

    def _rank(self, doc_id, n, threshold, candidates):
        if not candidates or n <= 0:
            return []
        query = self._query_vector(doc_id)
        if query is None or query.nnz == 0:
            return []
        matrix = self.tfidf_matrix[list(candidates)]
        product = (matrix @ query.T).tocoo()
        scores = np.zeros(len(candidates), dtype=float)
        scores[product.row] = product.data
        np.clip(scores, 0.0, 1.0, out=scores)
        eligible = np.flatnonzero(scores >= threshold)
        order = eligible[np.argsort(-scores[eligible], kind="stable")[:n]]
        results = []
        for position in order:
            bid = self._artifact["records"][candidates[position]]
            results.append({
                "bid_id": bid["id"],
                "title": bid["deliverables"] or bid["filename"],
                "organization_name": bid["organization_name"] or "",
                "announcement_date": bid["announcement_date"].isoformat() if bid["announcement_date"] else "",
                "budget_amount": bid["budget_amount"] or 0,
                "awarded_company": bid["awarded_company"] or "",
                "prefecture_code": bid["prefecture_code"] or "",
                "industry_category": bid["industry_category"] or "",
                "similarity_score": round(float(scores[position]), 4),
            })
        return results

    def _search(self, doc_id, n, threshold, months, prefecture_code, industry_category, cached):
        n = int(self.config.get("default_n", 10)) if n is None else int(n)
        threshold = float(self.config.get("default_threshold", 0.3)) if threshold is None else float(threshold)
        months = self._months(months)
        if n <= 0 or not self._ensure_built(months):
            return []
        candidates = self._candidate_indices(doc_id, months, prefecture_code, industry_category)
        candidate_digest = hashlib.sha256(np.asarray(candidates, dtype=np.int64).tobytes()).digest()
        key = (doc_id, n, threshold, months, prefecture_code, industry_category, candidate_digest)
        if cached:
            with _CACHE_LOCK:
                if key in self._similarity_cache:
                    self._similarity_cache.move_to_end(key)
                    return [dict(result) for result in self._similarity_cache[key]]
        result = self._rank(doc_id, n, threshold, candidates)
        if cached:
            with _CACHE_LOCK:
                self._similarity_cache[key] = result
                self._similarity_cache.move_to_end(key)
                while len(self._similarity_cache) > 100:
                    self._similarity_cache.popitem(last=False)
        return [dict(item) for item in result]

    def get_top_n_similar(
        self, doc_id: int, n: Optional[int] = None,
        threshold: Optional[float] = None, months: Optional[int] = None,
        prefecture_code: str = "", industry_category: str = "",
    ) -> List[Dict[str, Any]]:
        return self._search(doc_id, n, threshold, months, prefecture_code, industry_category, False)

    def get_cached_top_n(
        self, doc_id: int, n: Optional[int] = None,
        threshold: Optional[float] = None, months: Optional[int] = None,
        prefecture_code: str = "", industry_category: str = "",
    ) -> List[Dict[str, Any]]:
        return self._search(doc_id, n, threshold, months, prefecture_code, industry_category, True)

    def save_vectors(self, filepath: str | None = None) -> str:
        if not self._is_built:
            raise RuntimeError("Vectors not built. Call build() first.")
        filepath = filepath or os.path.join(self.cache_dir, "tfidf_vectors.pkl")
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        data = {key: value for key, value in self._artifact.items() if key != "results"}
        with open(filepath, "wb") as file:
            pickle.dump(data, file)
        return filepath

    def _load_vectors(self, filepath, fingerprint, months):
        automatic = filepath is None
        filepath = filepath or os.path.join(self.cache_dir, "tfidf_vectors.pkl")
        if not os.path.exists(filepath):
            return False
        try:
            with open(filepath, "rb") as file:
                data = pickle.load(file)
            if not self._compatible(data, fingerprint, months):
                return False
            if automatic and data["max_docs"] is not None:
                return False
            matrix = data["tfidf_matrix"]
            if not issparse(matrix) or matrix.shape[0] != len(data["doc_ids"]):
                return False
            if len(data["records"]) != len(data["doc_ids"]):
                return False
            if matrix.shape[1] != len(data["vectorizer"].get_feature_names_out()):
                return False
            data["tfidf_matrix"] = matrix.tocsr()
            data["indices"] = {doc_id: index for index, doc_id in enumerate(data["doc_ids"])}
            data["results"] = OrderedDict()
            self._publish(data)
            return self._is_built
        except (OSError, ValueError, TypeError, KeyError, AttributeError, EOFError, pickle.UnpicklingError) as exc:
            logger.warning("Failed to load vectors: %s", exc)
            return False

    def load_vectors(self, filepath: str | None = None) -> bool:
        self._reset()
        _, fingerprint = self._snapshot()
        filepath = filepath or os.path.join(self.cache_dir, "tfidf_vectors.pkl")
        return self._load_vectors(filepath, fingerprint, self._months(None))

    def compute_similarity_between_texts(self, text1: str, text2: str) -> float:
        if not self._ensure_built():
            return 0.0
        vec1, vec2 = self.vectorizer.transform([text1, text2])
        return round(float(np.clip(vec1.multiply(vec2).sum(), 0.0, 1.0)), 4)


def get_japanese_stop_words() -> List[str]:
    from config.japanese_stopwords import JAPANESE_STOP_WORDS
    return JAPANESE_STOP_WORDS
