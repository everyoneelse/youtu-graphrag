import time
from openai import OpenAI
from collections import Counter
import utils.call_llm_api as llm_api

class Eval:
    def __init__(self, llm_api_key):
        self.llm_api_key = llm_api_key
        
    def eval(self, question, gold_answer, answer):
        prompt = f"""
        You are an expert evaluator. Your task is to determine if the predicted answer is correct based on the question and gold answer.
        The criteria should be reasonable, not too strict or too lenient.
        
        Question: {question}
        Gold Answer: {gold_answer}
        Predicted Answer: {answer}
        
        Return only "1" (correct) or "0" (incorrect):
        """
        pass
        client = llm_api.call_llm_api(self.llm_api_key, False)
        return client.call_llm_api(prompt)
