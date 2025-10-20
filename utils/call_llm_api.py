import os
import time
import json
import requests
import re

from openai import OpenAI
from dotenv import load_dotenv

from utils.logger import logger

load_dotenv()

class LLMCompletionCall:
    def __init__(self, model=None, base_url=None, api_key=None, temperature=None):
        """
        Initialize LLM client with custom or environment configurations.
        
        Args:
            model: LLM model name (defaults to LLM_MODEL env var)
            base_url: API base URL (defaults to LLM_BASE_URL env var)
            api_key: API key (defaults to LLM_API_KEY env var)
            temperature: Temperature for generation (defaults to 0.3)
        """
        self.llm_model = model or os.getenv("LLM_MODEL", "deepseek-chat")
        self.llm_base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.llm_api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.temperature = temperature if temperature is not None else 0.3
        
        if not self.llm_api_key:
            raise ValueError("LLM API key not provided")
        
        self.client = OpenAI(base_url=self.llm_base_url, api_key=self.llm_api_key)
        
        logger.debug(f"Initialized LLM client: model={self.llm_model}, base_url={self.llm_base_url}")

    def call_api(self, content: str, temperature: float = None) -> str:
        """
        Call API to generate text with retry mechanism.
        
        Args:
            content: Prompt content
            temperature: Override default temperature for this call
            
        Returns:
            Generated text response
        """
        temp = temperature if temperature is not None else self.temperature
            
        try:
            completion = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": content}],
                temperature=temp
            )
            raw = completion.choices[0].message.content or ""
            clean_completion = self._clean_llm_content(raw)
            return clean_completion
            
        except Exception as e:
            logger.error(f"LLM api calling failed. Error: {e}")
            raise e 

    def _clean_llm_content(self, text: str) -> str:
        if not isinstance(text, str):
            return ""
        t = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        t = re.sub(r"[\u200B-\u200D\uFEFF]", "", t)
        fence_re = re.compile(r"^\s*```(?:\s*\w+)?\s*\n(?P<body>[\s\S]*?)\n\s*```\s*$", re.MULTILINE)
        m = fence_re.match(t)
        if m:
            t = m.group("body").strip()
        else:
            if t.startswith("```") and t.endswith("```") and len(t) >= 6:
                t = t[3:-3].strip()

        if t.lower().startswith("json\n"):
            t = t.split("\n", 1)[1].strip()

        return t