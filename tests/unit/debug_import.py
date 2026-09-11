import sys
import os
import traceback

print("Current working directory:", os.getcwd())
print("Sys.path:", sys.path)
print()
print("Checking if project root is in sys.path:")
project_root = '/home/herbmatsui/nyuusatsu'
print(f"  {project_root} in sys.path: {project_root in sys.path}")
print()
print("Checking if repositories directory exists:")
repos_path = os.path.join(project_root, 'repositories')
print(f"  {repos_path} exists: {os.path.exists(repos_path)}")
print(f"  {repos_path} is directory: {os.path.isdir(repos_path)}")
print()
print("Checking for __init__.py:")
init_path = os.path.join(repos_path, '__init__.py')
print(f"  {init_path} exists: {os.path.exists(init_path)}")
print()
print("Trying to import repositories...")
try:
    import repositories
    print("  SUCCESS: repositories imported")
    print(f"  repositories.__file__: {repositories.__file__}")
except Exception as e:
    print(f"  FAILED: {e}")
    traceback.print_exc()
print()
print("Trying to import repositories.agency_inventory_repository...")
try:
    from repositories.agency_inventory_repository import AgencyInventoryRepository
    print("  SUCCESS: AgencyInventoryRepository imported")
except Exception as e:
    print(f"  FAILED: {e}")
    traceback.print_exc()