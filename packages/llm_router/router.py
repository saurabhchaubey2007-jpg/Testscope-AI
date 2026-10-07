import os
import json
from contextvars import ContextVar
from pydantic import BaseModel
from typing import Type, TypeVar, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from apps.api.app.core.config import settings

T = TypeVar('T', bound=BaseModel)
active_provider: ContextVar[str | None] = ContextVar("llm_provider", default=None)

class FakeLLMProvider:
    def with_structured_output(self, schema: Type[T]):
        class FakeChain:
            def invoke(self, prompt: str) -> T:
                # Return dummy data based on schema
                if hasattr(schema, "fake"):
                    return schema.fake()
                return schema.model_construct()
        return FakeChain()
    
    def invoke(self, prompt: str):
        class FakeResponse:
            content = "Fake response"
        return FakeResponse()

def get_llm():
    provider = (active_provider.get() or settings.default_llm_provider).lower()
    
    if os.environ.get("USE_FAKE_LLM", str(settings.use_fake_llm).lower()) == "true":
        return FakeLLMProvider()
        
    if provider == "gemini":
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is not set")
        return ChatGoogleGenerativeAI(model=settings.gemini_model, google_api_key=settings.google_api_key, timeout=60, max_retries=2)
    elif provider == "groq":
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is not set")
        options = {"reasoning_effort": "low"} if settings.groq_model.startswith("openai/gpt-oss-") else {}
        return ChatGroq(model=settings.groq_model, api_key=settings.groq_api_key, timeout=60, max_retries=2, max_tokens=4096, **options)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")

def generate_structured(prompt: str, schema: Type[T]) -> T:
    llm = get_llm()
    if isinstance(llm, ChatGroq) and llm.model_name in {"openai/gpt-oss-120b", "openai/gpt-oss-20b"}:
        chain = llm.with_structured_output(schema, method="json_schema", strict=True)
    else:
        chain = llm.with_structured_output(schema)
    return chain.invoke(prompt)

def generate_text(prompt: str) -> str:
    llm = get_llm()
    response = llm.invoke(prompt)
    return response.content


def generate_python_suite(prompt: str, schema: Type[T], file_name: str) -> T:
    """Keep executable code out of JSON strings, which providers can mis-escape."""
    llm = get_llm()
    if isinstance(llm, FakeLLMProvider):
        return schema.fake()
    code = generate_python_code(prompt, llm)
    return schema.model_validate({"tests": [{"file_name": file_name, "code": code}]})


def generate_python_code(prompt: str, llm=None) -> str:
    llm = llm or get_llm()
    response = llm.invoke(prompt + "\nReturn only complete Python source for one self-contained test file. Do not return JSON. Put all fixtures and tests in this file.")
    if response.response_metadata.get("finish_reason") == "length":
        raise ValueError("LLM test code was truncated; reduce the suite size or increase the output token limit")
    code = response.content.strip()
    if code.startswith("```"):
        code = code.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return code + "\n"
