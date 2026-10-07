import os
import ast

def analyze_repository(repo_path: str) -> dict:
    if not os.path.exists(repo_path):
        raise ValueError(f"Repository path does not exist: {repo_path}")
        
    summary = {
        "files": 0,
        "modules": [],
        "functions": [],
        "classes": [],
        "existing_tests": [],
        "source_files": []
    }
    
    source_budget = 40000
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in {"venv", ".venv", ".git", "__pycache__", "node_modules", ".next", "dist", "build"}]
        if "venv" in root or ".git" in root or "__pycache__" in root:
            continue
            
        for file in files:
            relative_parts = os.path.relpath(root, repo_path).split(os.sep)
            is_test_source = "tests" in relative_parts or file.startswith("test_") or file.endswith("_test.py")
            if source_budget > 0 and not is_test_source and file.endswith((".py", ".tsx", ".jsx", ".ts", ".js", ".html")):
                source_path = os.path.join(root, file)
                if not os.path.islink(source_path):
                    try:
                        with open(source_path, encoding="utf-8") as source:
                            content = source.read(min(6000, source_budget))
                        summary["source_files"].append({"path": os.path.relpath(source_path, repo_path), "content": content})
                        source_budget -= len(content)
                    except (OSError, UnicodeError):
                        pass
            if file.endswith(".py"):
                summary["files"] += 1
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, repo_path)
                
                module_name = rel_path.replace(os.sep, ".").replace(".py", "")
                summary["modules"].append(module_name)
                
                if file.startswith("test_") or file.endswith("_test.py"):
                    summary["existing_tests"].append(rel_path)
                    
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        tree = ast.parse(f.read(), filename=file_path)
                        
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if not node.name.startswith("_"):
                                args = [arg.arg for arg in node.args.args]
                                summary["functions"].append({"name": node.name, "module": module_name, "args": args})
                        elif isinstance(node, ast.ClassDef):
                            if not node.name.startswith("_"):
                                summary["classes"].append({"name": node.name, "module": module_name})
                except SyntaxError:
                    pass
                except Exception as e:
                    print(f"Error parsing {file_path}: {e}")

    return summary
