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
        "existing_tests": []
    }
    
    for root, _, files in os.walk(repo_path):
        if "venv" in root or ".git" in root or "__pycache__" in root:
            continue
            
        for file in files:
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
                        if isinstance(node, ast.FunctionDef):
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
