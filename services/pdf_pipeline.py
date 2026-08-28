from pdfplumber import open as pdf_open
import tempfile
import logging
from typing import List, Optional

class PDFPipeline:
    """PDFからのテキスト抽出と正規化パイプライン"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def extract_text_from_pdf(self, pdf_url: str) -> str:
        """PDFからテキストを抽出"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                # PDFダウンロード
                response = await requests.get(pdf_url, timeout=30)
                tmp_file.write(response.content)
                tmp_file_path = tmp_file.name
            
            # テキスト抽出
            with pdf_open(tmp_file_path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() + " \n "
            return text.strip()
        except Exception as e:
            self.logger.error(f"PDF抽出失敗: {str(e)}")
            return ""
        finally:
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

    def extract_qualifications(self, text: str) -> List[Dict[str, Any]]:
        """ text から参加資格を抽出し正規化"""
        # 簡易実装（後で LLM 正規化を統合）
        qualifications = []
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("■QUALIFICATIONS") or "必要条件" in line:
                # 構造化可能なルールを適用（例: 番号付きリスト）
                if line.startswith("1.") or line.startswith("（") or line.startswith("-"):
                    qualification = {
                        "text": line,
                        "type": "UNMATCHED",
                        "confidence": 0.7
                    }
                    qualifications.append(qualification)
        return qualifications

    def write_qualifications_to_bid(self, bid_id: int, qualifications: List[Dict[str, Any]]):
        """Bidに資格情報を保存"""
        # 簡易実装
        # 実際は BidQualificationTag などのモデルを通じて保存
        pass
