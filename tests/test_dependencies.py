import importlib
import pkgutil
import services
import pytest

def test_no_circular_imports():
    """
    servicesパッケージ内のモジュールをインポートし、循環参照がないか確認する。
    """
    for loader, module_name, is_pkg in pkgutil.walk_packages(services.__path__, services.__name__ + "."):
        try:
            importlib.import_module(module_name)
        except ImportError as e:
            pytest.fail(f"循環参照またはインポートエラー: {module_name}, エラー: {e}")
