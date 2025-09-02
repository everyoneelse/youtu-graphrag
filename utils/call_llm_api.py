import time
import json
import requests
from openai import OpenAI

class call_llm_api:
    def __init__(self, llm_api_key, use_qwen: bool = False):
        self.llm_api_key = llm_api_key
        self.use_qwen = use_qwen
    
    def call_llm_api(self, content: str) -> str:
        if self.use_qwen:
            return self._call_qwen_api(content)
        else:
            return self._call_llm_api(self.llm_api_key, content)

    def _call_llm_api(self, llm_api_key, content: str) -> str:
        """
        Call OpenAI API to generate text with retry mechanism.
        
        Args:
            content: Prompt content
            
        Returns:
            Generated text response
        """
        if not llm_api_key:
            raise ValueError("LLM API key not provided")
            
        max_retries = 20
        retry_delay = 1  
        
        for attempt in range(max_retries):
            try:
                client = OpenAI(
                    api_key = llm_api_key,
                    base_url="https://api.lkeap.cloud.tencent.com/v1",
                )
                completion = client.chat.completions.create(
                    model="deepseek-v3-0324",
                    messages=[{"role": "user", "content": content}],
                    temperature=0.3
                )
                return completion.choices[0].message.content.strip("```").strip("json")
                
            except Exception as e:
                error_msg = str(e)
                print(f"LLM API call failed (attempt {attempt + 1}/{max_retries}): {error_msg}")
                
                if "rate limit" in error_msg.lower() or "429" in error_msg:
                    wait_time = retry_delay * (2 ** attempt)  
                    print(f"Rate limit detected, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                elif attempt < max_retries - 1:  
                    time.sleep(retry_delay)
                else:  
                    print(f"All retry attempts failed. Last error: {error_msg}")
                    raise e 

    def _call_qwen_api(self, content: str) -> str:
        """
        Call Qwen API to generate text with retry mechanism.
        
        Args:
            content: Prompt content
            
        Returns:
            Generated text response
        """
        url = "https://ms-6rpp85gl-100034032793-sw.gw.ap-shanghai.ti.tencentcs.com/ms-6rpp85gl/v1/chat/completions"
        
        data = {
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ]
        }
        
        headers = {"Content-Type": "application/json"}
        
        max_retries = 20
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=data, headers=headers)
                response.raise_for_status() 
                
                response_json = json.loads(response.text)
                res_text = response_json['choices'][0]['message']['content']
                
                # Remove think tags if present
                if '</think>' in res_text:
                    res_text = res_text.split('</think>', 1)[-1].strip()
                
                return res_text.strip("```").strip("json")
                
            except Exception as e:
                error_msg = str(e)
                print(f"Qwen API call failed (attempt {attempt + 1}/{max_retries}): {error_msg}")
                
                if "rate limit" in error_msg.lower() or "429" in error_msg:
                    wait_time = retry_delay * (2 ** attempt)
                    print(f"Rate limit detected, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                elif attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    print(f"All retry attempts failed. Last error: {error_msg}")
                    raise e
