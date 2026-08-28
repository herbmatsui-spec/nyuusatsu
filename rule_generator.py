"""
自治体ルール自動生成AIエンジン (rule_generator.py)

このスクリプトは、自治体の入札情報ページHTMLを解析し、
クローラーが利用可能なCSSセレクタ定義(JSON)をGemini APIを用いて自動生成します。
"""
# -*- coding: utf-8 -*-

import os
import json
import logging
import argparse
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai

# ---
# 定数定義
RULES_FILE = "crawl_rules.json"
ERROR_LOG = "error.log"
MODEL_ID = "gemini-3.1-flash-lite"

def setup_logging():
    """
    ロギング設定: コンソール出力と error.log ファイル出力の両方に行う
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(ERROR_LOG, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )

# ---
# Pydantic スキーマ定義
class CrawlerRule(BaseModel):
    agency_name: str = Field(description="自治体名（例：宇和島市、東京都下など）")
    start_url: str = Field(description="対象ページのURL")
    list_selector: str = Field(description="入札案件が並んでいるテーブルやリストの、1案件ごとの行を表すCSSセレクタ（例: table.list tr）")
    link_selector: str = Field(description="その行の中からPDFリンクを取得するためのCSSセレクタ（例: a[href$='.pdf']）")
    title_selector: str = Field(description="その行の中から案件タイトルを取得するためのCSSセレクタ")
    requires_js: bool = Field(description="ページ表示にJavaScriptのレンダリング（Playwrightの待機）が必要そうならTrue、不要そうならFalse")

# ---
# プロンプト定義
SYSTEM_PROMPT = """あなたは熟練のWebスクレイピングエンジニアです。
提供されたHTMLを解析し、特定の自治体の入札案件一覧ページから情報を抽出するための最適なCSSセレクタを特定してください。

【重要ルール】
1. セレクタは、できるだけユニークで堅牢なものを選択すること。
2. `list_selector` は、案件1件分を囲む最小の共通親要素（trやdivなど）であること。
3. `link_selector` と `title_selector` は、`list_selector` の内部で相対的に動作するものであること。
4. 日本語で思考し、構造化されたJSON形式で回答すること。
"""

USER_PROMPT_TEMPLATE = """
以下のURLのページのHTMLを解析し、クローラー設定ルールを生成してください。

URL: {url}

HTML内容:
---
{html}
---
"""

# ---
# Gemini クライアント・認証関連
def load_api_key():
    """
    .env または 環境変数から GEMINI_API_KEY を取得する
    """
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logging.error("GEMINI_API_KEY が設定されていません。.env ファイルを確認してください。")
        raise EnvironmentError("GEMINI_API_KEY is not set.")
    return api_key

def init_gemini_client():
    """
    Gemini クライアントを初期化して返す
    """
    try:
        api_key = load_api_key()
        client = genai.Client(api_key=api_key)
        logging.info("Gemini Client を正常に初期化しました。")
        return client
    except Exception as e:
        logging.exception(f"Gemini Client の初期化に失敗しました: {e}")
        raise

# ---
# HTML 読込機能
def load_html_from_file(path: str) -> str:
    """
    ローカルファイルからHTMLを読み込む
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"HTMLファイルが見つかりません: {path}")
    return p.read_text(encoding="utf-8")

def load_html_from_url(url: str) -> str:
    """
    URLからHTMLを取得する
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logging.exception(f"URLからHTMLの取得に失敗しました ({url}): {e}")
        raise

def load_html(url_or_path: str) -> str:
    """
    ファイルパスまたはURLを判定してHTMLを読み込む
    """
    if url_or_path.startswith(("http://", "https://")):
        logging.info(f"URLからHTMLを取得します: {url_or_path}")
        return load_html_from_url(url_or_path)
    else:
        logging.info(f"ファイルからHTMLを読み込みます: {url_or_path}")
        return load_html_from_file(url_or_path)

# ---
# Gemini 呼出機能
def generate_rule(client, url: str, html: str) -> CrawlerRule:
    """
    Gemini APIを用いてHTMLからクローラールールを生成する
    """
    logging.info(f"Geminiによるルール生成を開始します: {url}")
    
    # API呼び出し間隔制限 (Rate Limit回避)
    time.sleep(10)
    
    prompt = USER_PROMPT_TEMPLATE.format(url=url, html=html)
    
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config={
                "system_instruction": SYSTEM_PROMPT,
                "response_mime_type": "application/json",
                "response_schema": CrawlerRule,
            }
        )
        
        # google-genai SDK の .parsed を使用して Pydantic モデルとして取得
        rule = response.parsed
        if not rule:
            raise ValueError("Geminiからの応答にパース可能なルールが含まれていませんでした。")
            
        logging.info(f"ルールの生成に成功しました: {rule.agency_name}")
        return rule
        
    except Exception as e:
        logging.exception(f"Geminiによるルール生成中にエラーが発生しました ({url}): {e}")
        # error.log への書き出しは logging.exception で既に行われている
        raise

# ---
# ルール管理機能 (JSONマージ)
def load_rules(file_path: str) -> list:
    """
    既存のルールファイル(JSON)を読み込む。存在しない場合は空リストを返す。
    """
    p = Path(file_path)
    if not p.exists():
        logging.info(f"ルールファイルが見つかりません。新規作成します: {file_path}")
        return []
    
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.exception(f"ルールファイルの読み込みに失敗しました: {e}")
        return []

def save_rules(file_path: str, rules: list):
    """
    ルールリストをJSONファイルに保存する。
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=4)
        logging.info(f"ルールファイルを保存しました: {file_path}")
    except Exception as e:
        logging.exception(f"ルールファイルの保存に失敗しました: {e}")
        raise

def merge_rule(rules: list, new_rule: CrawlerRule) -> list:
    """
    agency_name をキーに、既存のルールを更新(upsert)する
    """
    new_rule_dict = new_rule.model_dump()
    agency = new_rule_dict["agency_name"]
    
    # 既存のルールから同一自治体を探す
    for i, rule in enumerate(rules):
        if rule.get("agency_name") == agency:
            logging.info(f"既存のルールを更新します: {agency}")
            rules[i] = new_rule_dict
            return rules
            
    logging.info(f"新規ルールを追加します: {agency}")
    rules.append(new_rule_dict)
    return rules

# ---
# メイン統合フロー
def main():
    """
    メイン実行関数: 引数解析 -> HTML読込 -> Gemini生成 -> マージ保存
    """
    setup_logging()
    
    parser = argparse.ArgumentParser(description="自治体クローラー設定自動生成AI")
    parser.add_argument("--url", help="解析対象のURL (指定された場合はURLからHTMLを取得)")
    parser.add_argument("--html", help="解析対象のHTMLファイルパス")
    parser.add_argument("--output", default=RULES_FILE, help=f"保存先JSONファイル (デフォルト: {RULES_FILE})")
    
    args = parser.parse_args()
    
    if not args.url and not args.html:
        parser.print_help()
        return

    try:
        # 1. HTMLの取得
        target_url = args.url if args.url else "unknown"
        if args.html:
            html_content = load_html(args.html)
        else:
            html_content = load_html(args.url)
            target_url = args.url
            
        # 2. Gemini Client 初期化
        client = init_gemini_client()
        
        # 3. ルール生成
        new_rule = generate_rule(client, target_url, html_content)
        
        # 4. ルールマージと保存
        rules = load_rules(args.output)
        updated_rules = merge_rule(rules, new_rule)
        save_rules(args.output, updated_rules)
        
        logging.info("すべての処理が正常に完了しました。")
        
    except Exception as e:
        logging.error(f"実行中に致命的なエラーが発生しました: {e}")
        exit(1)

if __name__ == "__main__":
    main()
