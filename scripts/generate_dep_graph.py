from pathlib import Path

def generate_mermaid_graph():
    services_dir = Path('services')
    lines = ["graph TD"]
    
    # 実際のファイルからノードを生成
    modules = []
    for py_file in services_dir.glob('*.py'):
        if py_file.name.startswith('_') or py_file.name == '__init__.py':
            continue
        modules.append(py_file.stem)
    
    for m in modules:
        lines.append(f"    {m}[{m}]")
    
    # 依存関係の定義 (分析スクリプトの結果に基づき適宜更新)
    # ここでは基本構造を定義
    deps = {
        "bid_analysis_service": ["llm_service", "bid_service"],
        "bid_service": ["bid_repository"],
        "crawl_service": ["agency_repository"],
        "llm_service": ["llm_provider"],
        "analysis_service": ["bid_analysis_service"],
    }
    
    for module, dep_list in deps.items():
        for dep in dep_list:
            # 定義されたモジュール間のみ矢印を引く
            if dep in modules:
                lines.append(f"    {module} --> {dep}")
    
    return "\n".join(lines)

if __name__ == '__main__':
    print(generate_mermaid_graph())
