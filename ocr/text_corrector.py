# -*- coding: utf-8 -*-
"""Step 31-34: 手動補正エディタ用のデータ管理"""
import os
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from .ocr_result import OCRResult, OCRBlock
from .logger import setup_ocr_logging

logger = setup_ocr_logging()


class TextCorrector:
    """OCR結果の手動補正を管理するクラス"""

    def __init__(self, config: Optional[Any] = None):
        # config could be OCRConfig or just passed storage_dir
        self.storage_dir = getattr(config, "correction_storage_dir", "corrected_texts")
        os.makedirs(self.storage_dir, exist_ok=True)

    def _make_file_id(self, source_path: str) -> str:
        """ファイルIDを生成"""
        return hashlib.md5(source_path.encode("utf-8")).hexdigest()

    def save_ocr_result(
        self,
        source_path: str,
        result: OCRResult,
        metadata: Optional[Dict] = None,
    ) -> str:
        """OCR結果を保存し、補正用IDを返す"""
        file_id = self._make_file_id(source_path)
        file_path = os.path.join(self.storage_dir, file_id + ".json")

        blocks_data = []
        for b in result.blocks:
            blocks_data.append({
                "text": b.text,
                "confidence": b.confidence,
                "page_number": b.page_number,
            })

        data = {
            "file_id": file_id,
            "source_path": source_path,
            "created_at": datetime.now().isoformat(),
            "metadata": metadata or {},
            "ocr_result": {
                "total_pages": result.total_pages,
                "average_confidence": result.average_confidence,
                "full_text": result.full_text,
                "blocks": blocks_data,
            },
            "corrections": [],
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("OCR result saved: %s", file_id)
        return file_id

    def load_for_correction(self, file_id: str) -> Dict[str, Any]:
        """Step 33: 補正用データを読み込み"""
        file_path = os.path.join(self.storage_dir, file_id + ".json")
        if not os.path.exists(file_path):
            raise FileNotFoundError("Correction data not found: " + file_id)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data

    def apply_correction(
        self,
        file_id: str,
        block_index: int,
        corrected_text: str,
        user: str = "unknown",
    ) -> Dict[str, Any]:
        """Step 32: ブロック別編集を適用"""
        file_path = os.path.join(self.storage_dir, file_id + ".json")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        blocks = data["ocr_result"]["blocks"]
        if block_index < 0 or block_index >= len(blocks):
            raise IndexError("Block index out of range: " + str(block_index))

        original_text = blocks[block_index]["text"]

        correction_entry = {
            "block_index": block_index,
            "original_text": original_text,
            "corrected_text": corrected_text,
            "user": user,
            "timestamp": datetime.now().isoformat(),
        }
        data["corrections"].append(correction_entry)

        blocks[block_index]["text"] = corrected_text

        full_text_parts = [b["text"] for b in blocks]
        data["ocr_result"]["full_text"] = "\n\n".join(full_text_parts)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(
            "Correction applied: file_id=%s, block=%d, user=%s",
            file_id, block_index, user
        )
        return correction_entry

    def get_corrected_text(self, file_id: str) -> str:
        """Step 34: 補正済みテキストを取得"""
        data = self.load_for_correction(file_id)
        return data["ocr_result"]["full_text"]

    def get_correction_history(self, file_id: str) -> List[Dict]:
        """補正履歴を取得"""
        data = self.load_for_correction(file_id)
        return data.get("corrections", [])

    def list_corrected_files(self) -> List[Dict[str, Any]]:
        """保存済みの補正ファイル一覧を取得"""
        files = []
        if not os.path.exists(self.storage_dir):
            return files

        for filename in os.listdir(self.storage_dir):
            if filename.endswith(".json"):
                file_path = os.path.join(self.storage_dir, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    files.append({
                        "file_id": data["file_id"],
                        "source_path": data["source_path"],
                        "created_at": data["created_at"],
                        "correction_count": len(data.get("corrections", [])),
                        "average_confidence": data["ocr_result"]["average_confidence"],
                    })
                except Exception:
                    continue

        return files
