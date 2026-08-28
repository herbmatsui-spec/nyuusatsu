import pytest
from utils.security import (
    sanitize_filename,
    mask_sensitive_data,
    validate_api_key,
    validate_url,
    validate_file_upload
)

def test_sanitize_filename_basic():
    assert sanitize_filename("normal_file.txt") == "normal_file.txt"
    assert sanitize_filename("file/with\\slashes") == "file_with_slashes"
    assert sanitize_filename('file:*?"<>:"|?.txt') == "file__________.txt"
    assert sanitize_filename("___leading_trailing___") == "leading_trailing"
    assert sanitize_filename("___multiple___underscores___") == "multiple___underscores"
    assert sanitize_filename("") == "unnamed"
    # Ensure length limit
    long = "a" * 300
    assert len(sanitize_filename(long)) == 255

def test_mask_sensitive_data_simple():
    data = {
        "username": "alice",
        "password": "secret",
        "api_key": "12345",
        "token": "abc",
        "authorization": "Bearer xyz",
        "normal": "value"
    }
    masked = mask_sensitive_data(data)
    assert masked["username"] == "alice"
    assert masked["password"] == "***"
    assert masked["token"] == "***"
    assert masked["authorization"] == "***"
    assert masked["normal"] == "value"

def test_mask_sensitive_data_nested():
    data = {
        "user": {
            "id": 1,
            "api_key": "secret",
            "details": {
                "token": "abc"
            }
        },
        "list": [
            {"password": "pwd"},
            "plain",
            {"nested": {"secret": "s"}}
        ]
    }
    masked = mask_sensitive_data(data)
    assert masked["user"]["api_key"] == "***"
    assert masked["user"]["details"]["token"] == "***"
    assert masked["list"][0]["password"] == "***"
    assert masked["list"][1] == "plain"
    assert masked["list"][2]["nested"]["secret"] == "***"

def test_mask_sensitive_data_custom_keys():
    data = {"key": "value", "custom": "secret"}
    masked = mask_sensitive_data(data, keys_to_mask=["custom"])
    assert masked["key"] == "value"
    assert masked["custom"] == "***"

def test_validate_api_key():
    # Valid keys
    assert validate_api_key("sk-" + "a"*48, "openai") is None
    assert validate_api_key("sk-" + "a"*48, "deepseek") is None
    assert validate_api_key("AIza" + "b"*35, "gemini") is None
    assert validate_api_key("a"*32, "azure") is None
    # Invalid keys
    assert validate_api_key("short", "openai") is not None
    assert validate_api_key("sk-" + "a"*47, "openai") is not None
    assert validate_api_key("sk-" + "a"*49, "openai") is not None
    # Unknown provider returns None (no validation)
    assert validate_api_key("anything", "unknown") is None

def test_validate_url():
    assert validate_url("http://example.com") is None
    assert validate_url("https://example.com/path") is None
    assert validate_url("http://localhost:8000") is None
    assert validate_url("") == "URLは空にできません。"
    assert validate_url("   ") == "URLは空にできません。"
    assert validate_url("ftp://example.com") == "URLスキームは['http', 'https']のいずれかにしてください。"
    assert validate_url("http://") == "有効なURLを入力してください。"
    assert validate_url("not a url") == "URLスキームは['http', 'https']のいずれかにしてください。"
    # Allow localhost
    assert validate_url("http://localhost:8000", allow_localhost=True) is None
    assert validate_url("http://example.com", allow_localhost=True) == "ローカルホストのみ許可されています。"
    assert validate_url("http://127.0.0.1:3000", allow_localhost=True) is None
    assert validate_url("http://[::1]:80", allow_localhost=True) is None
    assert validate_url("http://google.com", allow_localhost=True) == "ローカルホストのみ許可されています。"

def test_validate_file_upload(mocker):
    # Mock UploadedFile-like object
    mock_file = mocker.MagicMock()
    mock_file.type = "application/pdf"
    # size under limit
    mock_file.getbuffer().nbytes = 10 * 1024 * 1024  # 10 MB
    assert validate_file_upload(mock_file) is None
    # Over size
    mock_file.getbuffer().nbytes = 25 * 1024 * 1024  # 25 MB
    assert "ファイルサイズが大きすぎます" in validate_file_upload(mock_file, max_size_mb=20)
    # Wrong type
    mock_file.getbuffer().nbytes = 5 * 1024 * 1024
    mock_file.type = "text/plain"
    assert validate_file_upload(mock_file) == "PDFファイルのみアップロード可能です。"