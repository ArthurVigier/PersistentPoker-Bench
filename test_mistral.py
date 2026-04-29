import os
import json
from litellm import completion

os.environ["MISTRAL_API_KEY"] = os.getenv("MISTRAL_API_KEY")

messages = [
    {"role": "system", "content": "You are a poker agent. Return a JSON object with 'action' (call, fold, raise, check) and 'amount' (integer or null). Do not use markdown."},
    {"role": "user", "content": "You hold Ah Kh. The board is 7s 2c 9d. The pot is 100. It costs 20 to call. What is your action?"}
]

try:
    print("Sending request to Mistral Large 3...")
    response = completion(
        model="mistral/mistral-large-latest",
        messages=messages,
        max_tokens=200,
        temperature=0.0
    )
    content = response.choices[0].message.content
    print(f"Response received:\n{content}")
    print(f"JSON Parsed: {json.loads(content)}")
except Exception as e:
    print(f"Error: {e}")
