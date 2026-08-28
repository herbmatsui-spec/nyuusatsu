import os
import re
from pathlib import Path

def find_imports(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # 'from x import y' または 'import x' を抽出
    imports = re.findall(r'from\s+([\w\.]+)\s+import|import\s+([\w\.]+)', content)
    return [i[0] or i[1] for i in imports]

def analyze_services():
    services_dir = Path('services')
    deps = {}
    # 分析対象とするサービス名のリスト
    target_services = ['bid_service', 'llm_service', 'crawl_service', 'analysis_service', 'bid_analysis_service']
    
    for py_file in services_dir.glob('*.py'):
        if py_file.name.startswith('_') or py_file.name == '__init__.py':
            continue
        module_name = py_file.stem
        imports = find_imports(py_file)
        
        # インポートされたモジュールの中からtarget_servicesに含まれるものを抽出
        relevant_deps = []
        for imp in imports:
            for target in target_services:
                if target in imp:
                    relevant_deps.append(target)
        
        deps[module_name] = list(set(relevant_deps))
    return deps

if __name__ == '__main__':
    import json
    result = analyze_services()
    print(json.dumps(result, indent=2))
