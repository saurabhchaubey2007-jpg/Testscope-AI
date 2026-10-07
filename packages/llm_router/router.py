import os
import json
from pydantic import BaseModel
from typing import Type, TypeVar, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from apps.api.app.core.config import settings

T = TypeVar('T', bound=BaseModel)

class FakeLLMProvider:
    def with_structured_output(self, schema: Type[T]):
        class FakeChain:
            def invoke(self, prompt: str) -> T:
                # Return dummy data based on schema
                return schema.construct()
        return FakeChain()
    
    def invoke(self, prompt: str):
        class FakeResponse:
            content = "Fake response"
        return FakeResponse()

def get_llm():
    provider = settings.default_llm_provider.lower()
    
    if os.environ.get("USE_FAKE_LLM") == "true":
        return FakeLLMProvider()
        
    if provider == "gemini":
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is not set")
        return ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=settings.google_api_key)
    elif provider == "groq":
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is not set")
        return ChatGroq(model="openai/gpt-oss-120b", api_key=settings.groq_api_key)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")

def generate_structured(prompt: str, schema: Type[T]) -> T:
    llm = get_llm()
    chain = llm.with_structured_output(schema)
    return chain.invoke(prompt)

def generate_text(prompt: str) -> str:
    llm = get_llm()
    response = llm.invoke(prompt)
    return response.content
