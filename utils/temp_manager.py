# 改善点1 ステップ7-9: utils/temp_manager.py
# クロール中に生成される一時的なPDFファイルの保存先を管理し、処理後にクリーンアップします。

import os
import shutil
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("TempDirManager")

class TempDirManager:
    """
    一時的なディレクトリの作成とクリーンアップを管理するクラス。
    """
    def __init__(self, base_dir: str = "temp_pdfs"):
        self.base_dir = Path(base_dir)
        # 起動時にベースディレクトリを作成
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create(self) -> Path:
        """
        日時ベースの一意な一時ディレクトリを作成し、そのパスを返す。
        例: temp_pdfs/20260708_153045_abcd123/
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        dir_name = f"{timestamp}_{unique_id}"
        target_dir = self.base_dir / dir_name
        
        target_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created temporary directory: {target_dir}")
        return target_dir

    def cleanup(self, path: Path):
        """
        指定された一時ディレクトリとその中身を完全に削除する。
        """
        try:
            if path.exists() and path.is_dir():
                shutil.rmtree(path)
                logger.info(f"Cleaned up temporary directory: {path}")
            else:
                logger.warning(f"Cleanup failed: {path} does not exist or is not a directory")
        except Exception as e:
            logger.error(f"Error during cleanup of {path}: {e}")
