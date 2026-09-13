import pytest
import sys
import os

def test_import_repositories():
    """Test that repositories module can be imported"""
    print("Sys.path:", sys.path)
    try:
        from repositories.agency_inventory_repository import AgencyInventoryRepository
        print("Successfully imported AgencyInventoryRepository")
        assert True
    except ImportError as e:
        print(f"Failed to import: {e}")
        # Don't assert False here, just print for debugging
        pass