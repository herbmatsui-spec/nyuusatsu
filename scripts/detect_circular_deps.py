import os
import re
from pathlib import Path
from collections import defaultdict

def get_local_imports(file_path, package='services'):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # 'from services.x import y' または 'import services.x' を抽出
    pattern = rf'from\s+{package}\.(\w+)\s+import|import\s+{package}\.(\w+)'
    matches = re.findall(pattern, content)
    return [m[0] or m[1] for m in matches]

def detect_cycles():
    services_dir = Path('services')
    graph = defaultdict(list)
    
    for py_file in services_dir.glob('*.py'):
        if py_file.name.startswith('_') or py_file.name == '__init__.py':
            continue
        module = py_file.stem
        imports = get_local_imports(py_file)
        for imp in imports:
            graph[module].append(imp)
    
    visited = set()
    rec_stack = set()
    cycles = []
    
    def dfs(node, path):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor, path + [node]):
                    return True
            elif neighbor in rec_stack:
                cycles.append(path + [node, neighbor])
        rec_stack.remove(node)
        return False
    
    for node in list(graph.keys()):
        if node not in visited:
            dfs(node, [])
    
    return cycles

if __name__ == '__main__':
    cycles = detect_cycles()
    if cycles:
        print("循環参照 detected:")
        for c in cycles:
            print(" -> ".join(c))
    else:
        print("循環参照なし")
