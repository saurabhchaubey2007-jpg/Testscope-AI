import os
import uuid
from pydantic import BaseModel, Field
from typing import List
from packages.llm_router.router import generate_structured
from apps.api.app.core.config import settings

class GeneratedTest(BaseModel):
    file_name: str = Field(description="Name of the test file, must start with test_")
    code: str = Field(description="The complete python code for the test file using pytest")

class GeneratedTestSuite(BaseModel):
    tests: List[GeneratedTest]

def generate_tests(test_plan: dict, repository_path: str, run_id: str) -> list:
    prompt = f"""
    Based on the following test plan, generate pytest code for the repository.
    Rules:
    - Only generate tests.
    - Prefer deterministic tests.
    - Do not generate arbitrary shell commands.
    - Do not use dangerous filesystem/network operations.
    - Use mocks where external services would otherwise be required.
    - Import the modules appropriately assuming the root of the repository is in PYTHONPATH.
    
    Test Plan:
    {test_plan}
    """
    
    suite = generate_structured(prompt, GeneratedTestSuite)
    
    generated_dir = os.path.join(settings.workspace_dir, "generated_tests", run_id)
    os.makedirs(generated_dir, exist_ok=True)
    
    results = []
    for test in suite.tests:
        if not test.file_name.startswith("test_"):
            test.file_name = "test_" + test.file_name
        if not test.file_name.endswith(".py"):
            test.file_name += ".py"
            
        file_path = os.path.join(generated_dir, test.file_name)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(test.code)
            
        results.append({
            "name": test.file_name,
            "file_path": file_path,
            "test_code": test.code
        })
        
    return results
