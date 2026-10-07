import json
from pydantic import BaseModel, Field
from typing import List
from packages.llm_router.router import generate_structured

class TestTarget(BaseModel):
    name: str = Field(description="Name of the test target (e.g., function or class name)")
    target_type: str = Field(description="Type: 'function', 'class', 'api'")
    description: str = Field(description="Description of what should be tested")
    priority: str = Field(description="High, Medium, Low")

class TestPlan(BaseModel):
    important_functions: List[TestTarget] = Field(default_factory=list)
    normal_cases: List[str] = Field(default_factory=list)
    edge_cases: List[str] = Field(default_factory=list)
    invalid_inputs: List[str] = Field(default_factory=list)
    integration_points: List[str] = Field(default_factory=list)
    recommended_tests: List[str] = Field(default_factory=list)

def create_test_plan(codebase_summary: dict) -> dict:
    prompt = f"""
    Analyze the following Python codebase summary and generate a structured test plan.
    Identify important functions/classes, normal cases, edge cases, invalid inputs, 
    integration points, and specific recommended pytest tests.
    
    Codebase Summary:
    {json.dumps(codebase_summary, indent=2)}
    """
    
    plan = generate_structured(prompt, TestPlan)
    return plan.model_dump()
