import os
import time
import json
import requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMCompletionCall:
    def __init__(self):
        self.llm_model = os.getenv("LLM_MODEL", "deepseek-chat")
        self.llm_base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.llm_api_key = os.getenv("LLM_API_KEY", "")
        if not self.llm_api_key:
            raise ValueError("LLM API key not provided")
        self.client = OpenAI(base_url=self.llm_base_url, api_key = self.llm_api_key)

    def call_api(self, content: str) -> str:
        """
        Call API to generate text with retry mechanism.
        
        Args:
            content: Prompt content
            
        Returns:
            Generated text response
        """
            
        try:
            completion = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": content}],
                temperature=0.3
            )
            clean_completion = completion.choices[0].message.content.strip("```").strip("json")
            return clean_completion
            
        except Exception as e:
            print(f"LLM api calling failed. Error: {e}")
            raise e 