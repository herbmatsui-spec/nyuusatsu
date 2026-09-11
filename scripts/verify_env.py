import os
from dotenv import load_dotenv
from config_dir import AppConfig

def verify_env():
    """
    .env ファイルの内容が AppConfig で必要とする環境変数と整合しているか検証する。
    """
    load_dotenv()
    config = AppConfig()
    
    # 必須チェックリスト (config.py や各サービスで利用されているキー)
    required_keys = [
        "DEEPSEEK_API_KEY",
        "GEMINI_API_KEY",
        "DATABASE_URL",
        # OCR-related (Optional but checked if provider is set)
        "OCR_PROVIDER",
        "TESSERACT_CMD",
        "AZURE_DOC_INT_ENDPOINT",
        "AZURE_DOC_INT_KEY"
    ]
    
    missing_keys = []
    for key in required_keys:
        if not os.getenv(key):
            # OCR_PROVIDER が設定されていない場合は Tesseract がデフォルトなので警告のみ
            if key in ["TESSERACT_CMD", "AZURE_DOC_INT_ENDPOINT", "AZURE_DOC_INT_KEY"]:
                provider = os.getenv("OCR_PROVIDER", "tesseract")
                if provider == "tesseract" and key != "TESSERACT_CMD":
                    continue
                if provider == "azure" and key != "AZURE_DOC_INT_ENDPOINT" and key != "AZURE_DOC_INT_KEY":
                    continue
            missing_keys.append(key)
            
    if missing_keys:
        print(f"❌ Missing environment variables: {', '.join(missing_keys)}")
        raise EnvironmentError(f"Missing required environment variables: {missing_keys}")
    
    print("✅ Environment verification successful.")

if __name__ == "__main__":
    verify_env()
