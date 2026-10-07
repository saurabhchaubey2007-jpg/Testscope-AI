import os
from pydantic import BaseModel, Field
from packages.llm_router.router import generate_structured

class RepairedTest(BaseModel):
    patch: str = Field(description="The complete new python code for the test file")
    explanation: str = Field(description="Why this change fixes the test")

def repair_tests(failures: list, execution_results: dict, generated_tests: list, codebase_summary: dict) -> list:
    repairs = []
    
    test_code_map = {t["name"]: t for t in generated_tests}
    
    for failure in failures:
        if failure["category"] != "TEST_DEFECT":
            continue
            
        test_name = failure["test_name"]
        test = test_code_map.get(test_name)
        if not test:
            continue
            
        result = execution_results.get(test_name)
        if not result:
            continue
            
        prompt = f"""
        Fix this test code. It was classified as a TEST_DEFECT.
        
        Original Test Code:
        {test["test_code"]}
        
        Failure Output:
        {result["stdout"]}
        {result["stderr"]}
        
        Failure Explanation:
        {failure["explanation"]}
        
        Codebase context:
        {codebase_summary}
        
        Rules:
        - Return the FULL complete python code for the test file.
        - Do not modify application code.
        - Only output valid python code for the test file in the 'patch' field.
        """
        
        try:
            repair = generate_structured(prompt, RepairedTest)
            
            # Save the repaired test
            with open(test["file_path"], "w", encoding="utf-8") as f:
                f.write(repair.patch)
                
            # Update the generated test code in memory so rerun uses it
            test["test_code"] = repair.patch
                
            repairs.append({
                "test_name": test_name,
                "patch": repair.patch,
                "explanation": repair.explanation
            })
        except Exception as e:
            print(f"Error repairing {test_name}: {e}")
            
    return repairs
