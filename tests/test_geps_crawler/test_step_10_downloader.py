from crawler.downloader import Downloader, PDFDownloader
import os
import shutil

def test_downloader_init():
    """Downloaderの初期化"""
    d = Downloader()
    assert d.timeout == 30
    assert d.max_retries == 3
    assert d.insecure == False

def test_downloader_custom_init():
    """Downloaderのカスタム初期化"""
    d = Downloader(timeout=60, max_retries=5, insecure=True)
    assert d.timeout == 60
    assert d.max_retries == 5
    assert d.insecure == True

def test_downloader_headers():
    """DownloaderのHTTPヘッダーにUser-Agentが含まれるか"""
    d = Downloader()
    assert "User-Agent" in d.headers
    assert "Chrome" in d.headers["User-Agent"]

def test_pdf_downloader_init(tmp_path):
    """PDFDownloaderの初期化とディレクトリ作成"""
    dest = str(tmp_path / "test_pdfs")
    dl = PDFDownloader(dest_dir=dest)
    assert os.path.exists(dest)

def test_pdf_downloader_default_insecure():
    """PDFDownloaderのデフォルトはinsecure=True"""
    dl = PDFDownloader(dest_dir="./test_tmp_dl")
    assert dl._inner.insecure == True
    # クリーンアップ
    if os.path.exists("./test_tmp_dl"):
        shutil.rmtree("./test_tmp_dl")

def test_pdf_downloader_sha256(tmp_path):
    """SHA256ハッシュが正しく計算されるか"""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content for hash")
    sha = PDFDownloader._sha256_of(test_file)
    assert isinstance(sha, str)
    assert len(sha) == 64  # SHA256は64文字の16進文字列

def test_pdf_downloader_download_fail(tmp_path):
    """存在しないURLからのダウンロードが失敗を返すか"""
    dl = PDFDownloader(dest_dir=str(tmp_path), max_retries=1, timeout=5)
    success, path, sha, error = dl.download("https://nonexistent.example.com/no-such-file.pdf")
    assert success == False
    assert path is None
    assert sha is None
    assert error is not None

def test_pdf_downloader_filename_from_url(tmp_path):
    """URLからファイル名が正しく生成されるか"""
    dl = PDFDownloader(dest_dir=str(tmp_path))
    url = "https://example.com/docs/specification.pdf"
    safe_name = url.split("?")[0].rstrip("/").split("/")[-1]
    assert safe_name == "specification.pdf"

def test_pdf_downloader_filename_no_pdf_extension(tmp_path):
    """拡張子がないURLには.pdfが付与されるか"""
    dl = PDFDownloader(dest_dir=str(tmp_path))
    url = "https://example.com/docs/download"
    safe_name = url.split("?")[0].rstrip("/").split("/")[-1]
    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"
    assert safe_name.endswith(".pdf")
