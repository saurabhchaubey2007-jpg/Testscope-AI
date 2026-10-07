import os
import subprocess
import time
import sys

def run_pytest(test_files: list, repository_path: str) -> dict:
    results = {}
    
    env = os.environ.copy()
    env["PYTHONPATH"] = repository_path
    
    for test in test_files:
        file_path = test["file_path"]
        name = test["name"]
        
        start_time = time.time()
        
        try:
            process = subprocess.run(
                [sys.executable, "-m", "pytest", file_path, "-v", "--tb=short"],
                capture_output=True,
                text=True,
                env=env,
                timeout=30
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            status = "PASSED" if process.returncode == 0 else "FAILED"
            
            results[name] = {
                "status": status,
                "stdout": process.stdout,
                "stderr": process.stderr,
                "duration_ms": duration_ms
            }
            
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            results[name] = {
                "status": "TIMEOUT",
                "stdout": "",
                "stderr": "Test execution timed out after 30 seconds",
                "duration_ms": duration_ms
            }
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            results[name] = {
                "status": "ERROR",
                "stdout": "",
                "stderr": str(e),
                "duration_ms": duration_ms
            }
            
    return results
