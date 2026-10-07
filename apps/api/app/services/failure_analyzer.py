from pydantic import BaseModel, Field
from packages.llm_router.router import generate_structured
import re

class FailureAnalysis(BaseModel):
    category: str = Field(description="Must be one of: TEST_DEFECT, APP_DEFECT, ENV_FAILURE, FLAKY")
    explanation: str = Field(description="Explanation of the failure")
    evidence: list[str] = Field(description="Evidence supporting the classification (e.g. stack trace snippet)")
    needs_review: bool = Field(description="Whether human review is needed")

def deterministic_classify(stdout: str, stderr: str) -> str | None:
    output = stdout + "\n" + stderr
    
    # Simple deterministic rules
    if "ModuleNotFoundError" in output or "ImportError" in output:
        return "TEST_DEFECT"
    if "SyntaxError" in output or "IndentationError" in output:
        return "TEST_DEFECT"
    if "fixture" in output and "not found" in output:
        return "TEST_DEFECT"
        
    return None

def analyze_failures(execution_results: dict, generated_tests: list) -> list:
    analysis_list = []
    
    # Create lookup for test code
    test_code_map = {t["name"]: t["test_code"] for t in generated_tests}
    
    for name, result in execution_results.items():
        if result["status"] in ["PASSED", "TIMEOUT", "ERROR"]:
            continue
            
        test_code = test_code_map.get(name, "")
        stdout = result["stdout"]
        stderr = result["stderr"]
        
        # 1. Try deterministic
        category = deterministic_classify(stdout, stderr)
        
        if category:
            analysis_list.append({
                "test_name": name,
                "category": category,
                "explanation": "Determined by deterministic static rules",
                "evidence": [],
                "needs_review": False
            })
            continue
            
        # 2. Use LLM for ambiguous failures
        prompt = f"""
        Analyze this test failure and classify it.
        Categories: TEST_DEFECT, APP_DEFECT, ENV_FAILURE, FLAKY.
        
        Test Code:
        {test_code}
        
        Stdout:
        {stdout}
        
        Stderr:
        {stderr}
        """
        
        try:
            analysis = generate_structured(prompt, FailureAnalysis)
            
            # Ensure valid category
            cat = analysis.category if analysis.category in ["TEST_DEFECT", "APP_DEFECT", "ENV_FAILURE", "FLAKY"] else "TEST_DEFECT"
            
            analysis_list.append({
                "test_name": name,
                "category": cat,
                "explanation": analysis.explanation,
                "evidence": analysis.evidence,
                "needs_review": analysis.needs_review
            })
        except Exception as e:
            analysis_list.append({
                "test_name": name,
                "category": "TEST_DEFECT",
                "explanation": f"Failed to analyze: {str(e)}",
                "evidence": [],
                "needs_review": True
            })
            
    return analysis_list
