from google import genai
from google.genai import types
import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class QualificationTag:
    """正規化された参加資格タグ"""
    tag_code: str = ""
    display_name: str = ""
    category: str = ""
    description: str = ""

class BidNormalizer:
    """LLMを使用して未処理の入札情報を正規化し、構造化データに変換"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = None
            logging.getLogger(__name__).warning("BidNormalizer initialized without api_key")
        self.extract_metrics_prompt = """
You are a specialist in bid analysis. Your task is to extract structured information from bid documentation text.
Return ONLY a JSON object matching this schema:
{schema}
Do not include any explanation or additional text.

Available fields:
- budget: Budget limit or estimated price
- qualifications: Required qualifications or eligibility criteria
- deadline: Submission deadline or performance period
- deliverables: Required outputs or deliverables
- justification: Why this bid matters (optional)

Extract all available quantitative information with proper units.
Extract qualitative requirements as precise text.
Never invent information not explicitly stated.
"""
        self.normalize_prompt = """
You are a specialist in bid qualification normalization. 
Your task is to map fragmented qualification text to standardized procurement categories.
Use this rule: 
1. Map to the most precise publicly available category (unified qualification, industry permit, experience requirement)
2. If no clear match, return "UNMATCHED" 
3. Return ONLY the tag_code and confidence_score fields as JSON

Standard categories reference (use these exact codes):
- U_QUAL_A: 全省庁統一資格 ランクA
- U_QUAL_B: 全省庁統一資格 ランクB  
- U_QUAL_C: 全省庁統一資格 ランクC
- LIC_CONSTRUCTION_A: 建設業許可（特定建設業）
- LIC_TELECOM: 電気通信事業許可
- EXP_BPO_3Y: BPO業務経験3年以上
- SEC_INFO: ISO27001認証取得

Example mappings:
- "5年以上のシステム開発経験" -> EXP_BPO_3Y (confidence 0.95)
- "全省庁統一資格を保有" -> U_QUAL_A (confidence 0.98)
- "普通自動車運転免許" -> U_QUAL_C (confidence 0.85)

Return JSON only:
{{"tag_code": "UNMATCHED", "confidence_score": 0.0}}
"""

    def extract_bid_metrics(self, bid_text: str) -> Dict[str, Any]:
        """入札情報からメトリクスを抽出"""
        try:
            setup = {
                "files": [
                    {
                        "path": "bid_metrics schema.json",
                        "type": "application/json"
                    }
                ],
                "mimetype": "application/json",
                "text": self.extract_metrics_prompt,  # schema would be loaded from file in real implementation
                "participants": []
            }
            
            resp = self.client.analyze(
                prompt=f"Extract structured bid metrics from this text:<{bid_text}>\nReturn JSON following schema.",
                multimodal=False,
                raw=True
            )
            
            result = json.loads(resp)
            return result
            
        except Exception as e:
            logger.error(f"Extraction failed: {str(e)}")
            return {}

    def normalize_qualification(self, qualification_text: str) -> List[QualificationTag]:
        """参加資格を標準タグに正規化"""
        results = []
        
        # ローカルモデルによる正規化（低性能LLaMAベース）
        try:
            # LLM APIを使用した簡易実装
            setup = {
                "raw": {
                    "messages": [
                        {
                            "role": "user",
                            "content": f"{self.normalize_prompt} Input: {qualification_text}"
                        }
                    ],
                    "model": "openrouter/free",  # 低性能モデル
                }
            }
            
            resp = self.client.analyze(**setup["raw"])
            response_text = str(resp)
            
            try:
                json_result = json.loads(response_text)
                tag_code = json_result.get("tag_code", "UNMATCHED")
                confidence = json_result.get("confidence_score", 0.0)
                
                if tag_code != "UNMATCHED" or confidence > 0.1:
                    # 標準タグマッピング（簡易版）
                    tag_mapping = {
                        "埋没": "U_QUAL_C",
                        "全省庁統一資格": "U_QUAL_A", 
                        "保持資格": "U_QUAL_B",
                        "土木工事許可": "LIC_CONSTRUCTION_A",
                        "電気通信工事": "LIC_TELECOM",
                        "BPO経験": "EXP_BPO_3Y",
                        "ISO認証": "SEC_INFO"
                    }
                    
                    mapped_code = tag_mapping.get(tag_code, tag_code)
                    
                    # 標準タグ詳細データ
                    standard_tags = self._load_standard_tags()
                    if mapped_code in standard_tags:
                        tag_data = standard_tags[mapped_code]
                        results.append(QualificationTag(
                            tag_code=mapped_code,
                            display_name=tag_data["display_name"],
                            category=tag_data["category"],
                            description=tag_data["description"]
                        ))
            except json.JSONDecodeError:
                # 簡易マッピング
                tag_code = "U_QUAL_C"  # デフォルト
                if "土木" in qualification_text:
                    tag_code = "LIC_CONSTRUCTION_A"
                elif "電気通信" in qualification_text:
                    tag_code = "LIC_TELECOM"
                    
                # 標準タグデータ取得できなかった場合は空データ
                standard_tags = self._load_standard_tags()
                tag_data = standard_tags.get(tag_code, {})
                
                results.append(QualificationTag(
                    tag_code=tag_code,
                    display_name=tag_data.get("display_name", tag_code),
                    category=tag_data.get("category", "未分類"),
                    description=tag_data.get("description", "")
                ))
                
        except Exception as e:
            logger.error(f"Normalization failed: {str(e)}")
        
        return results
    
    def _load_standard_tags(self) -> Dict[str, Dict]:
        """標準タグマスターを返す"""
        return {
            "U_QUAL_A": {
                "display_name": "全省庁統一資格 ランクA",
                "category": "統一資格",
                "description": "国家レベルの最高等級資格"
            },
            "U_QUAL_B": {
                "display_name": "全省庁統一資格 ランクB", 
                "category": "統一資格",
                "description": "中規模プロジェクト対象ランク"
            },
            "U_QUAL_C": {
                "display_name": "全省庁統一資格 ランクC",
                "category": "統一資格",
                "description": "小規模プロジェクト対象ランク"
            },
            "LIC_CONSTRUCTION_A": {
                "display_name": "建設業許可（特定建設業",
                "category": "業種許可",
                "description": "道路・土木工事等の実績ある業者"
            },
            "LIC_TELECOM": {
                "display_name": "電気通信事業許可",
                "category": "業種許可",
                "description": "ネットワーク構築・保守の実績"
            },
            "EXP_BPO_3Y": {
                "display_name": "BPO業務経験3年以上",
                "category": "経験要件",
                "description": "コールセンター等の業務経験"
            },
            "SEC_INFO": {
                "display_name": "ISO27001認証取得",
                "category": "セキュリティ",
                "description": "情報セキュリティマネジメント"
            }
        }