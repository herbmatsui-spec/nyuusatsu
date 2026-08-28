"""Step 35: app.py統合用ヘルパー

app.pyの extract_text_from_pdf 関数を置き換えるための参考実装。
以下のように app.py で差し替え可能:

    from ocr import ocr_extract_text

    def extract_text_from_pdf(pdf_file: io.BytesIO) -> str:
        pdf_file.seek(0)
        data = pdf_file.read()
        return ocr_extract_text(data, source_name="uploaded_pdf")
"""
from typing import Callable


def patch_extract_function(module_path: str = "app", func_name: str = "extract_text_from_pdf") -> bool:
    """既存モジュールのテキスト抽出関数をOCR対応版に差し替える

    Args:
        module_path: 対象モジュール名 (例: "app")
        func_name: 差し替え対象の関数名

    Returns:
        差し替え成功時 True
    """
    import importlib
    from ocr import ocr_extract_text

    try:
        module = importlib.import_module(module_path)

        def ocr_aware_extract(pdf_file, *args, **kwargs):
            import io
            try:
                pdf_file.seek(0)
            except Exception:
                pass
            data = pdf_file.read() if hasattr(pdf_file, "read") else pdf_file
            return ocr_extract_text(data, source_name=module_path)

        setattr(module, func_name, ocr_aware_extract)
        return True
    except Exception as e:
        print(f"パッチ適用エラー: {e}")
        return False


if __name__ == "__main__":
    success = patch_extract_function()
    print(f"app.py統合パッチ: {'成功' if success else '失敗'}")
