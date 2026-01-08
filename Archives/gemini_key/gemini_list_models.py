import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GOOGLE_API")
if not api_key:
    raise RuntimeError("Please set GOOGLE_API in your environment (or .env).")

genai.configure(api_key=api_key)

# List available models
models = genai.list_models()
print("Available Gemini models:")
for m in models:
    print("-", m.name)