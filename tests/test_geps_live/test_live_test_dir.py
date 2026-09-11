from pathlib import Path


def test_live_test_dir_is_created(live_test_dir):
    assert isinstance(live_test_dir, Path)
    assert live_test_dir.is_dir()


def test_live_test_dir_can_be_retained(live_test_dir, request):
    request.node._live_test_dir_failed = True
    assert live_test_dir.is_dir()
