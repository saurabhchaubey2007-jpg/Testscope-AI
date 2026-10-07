import os
import subprocess
import time
import sys
import tempfile
from packages.testing.result_parser import parse_junit_xml

def run_pytest(test_files: list, repository_path: str, extra_args: list | None = None,
               artifacts_dir: str | None = None, timeout: int = 30) -> dict:
    """Run each generated test file with pytest.

    extra_args:    additional pytest CLI args (e.g. Playwright's --base-url).
    artifacts_dir: if set, each test gets an --output sub-directory here
                   (used by pytest-playwright for screenshots/traces).
    """
    results = {}
    
    env = os.environ.copy()
    env["PYTHONPATH"] = repository_path
    
    for test in test_files:
        file_path = test["file_path"]
        name = test["name"]
        
        start_time = time.time()

        cmd = [sys.executable, "-m", "pytest", file_path, "-v", "--tb=short", "-p", "no:cacheprovider"]
        test_artifacts_dir = None
        if artifacts_dir:
            test_artifacts_dir = os.path.join(artifacts_dir, os.path.splitext(name)[0])
            cmd += ["--output", test_artifacts_dir]
        if extra_args:
            cmd += extra_args
        
        try:
            with tempfile.TemporaryDirectory(prefix="testscope-results-") as result_dir:
                junit_path = os.path.join(result_dir, "results.xml")
                process = subprocess.run(
                    cmd + [f"--junitxml={junit_path}"], capture_output=True,
                    text=True, env=env, timeout=timeout,
                )
                cases = parse_junit_xml(junit_path)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            status = "PASSED" if process.returncode == 0 else "FAILED"
            
            results[name] = {
                "status": status,
                "stdout": process.stdout,
                "stderr": process.stderr,
                "duration_ms": duration_ms,
                "artifacts": _collect_artifacts(test_artifacts_dir),
                "cases": cases,
            }
            
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            results[name] = {
                "status": "TIMEOUT",
                "stdout": "",
                "stderr": f"Test execution timed out after {timeout} seconds",
                "duration_ms": duration_ms,
                "artifacts": _collect_artifacts(test_artifacts_dir),
            }
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            results[name] = {
                "status": "ERROR",
                "stdout": "",
                "stderr": str(e),
                "duration_ms": duration_ms,
                "artifacts": [],
            }
            
    return results


def _collect_artifacts(directory: str | None) -> list:
    """Return absolute paths of screenshots/traces/videos produced for a test."""
    if not directory or not os.path.isdir(directory):
        return []
    found = []
    for root, _, files in os.walk(directory):
        for f in files:
            if f.endswith((".png", ".jpg", ".zip", ".webm")):
                found.append(os.path.abspath(os.path.join(root, f)))
    return sorted(found)
