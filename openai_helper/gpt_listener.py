import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not found in .env")

client = OpenAI(api_key=OPENAI_API_KEY)

#function to ask GPT for analysis
def ask_gpt(chat_text: str) -> str:
    prompt = f"""You are myself who talks with my friends in natural manner.
Conversation:
{chat_text}

Respond clearly, VERYVERY VERY shortly and be friendly. ANSWER ONLY IN RUSSIAN LANGUAGE. 
"""
    response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], temperature=0.7)
    return response.choices[0].message.content
