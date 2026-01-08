import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GOOGLE_API")
if not api_key:
    raise RuntimeError("Please set GOOGLE_API in your environment (or .env).")

genai.configure(api_key=api_key)

# List of models to test (vision/text only, filter as needed)
models_to_test = [
    "models/gemini-2.5-pro",
    "models/gemini-2.5-flash",
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-lite",
    "models/gemini-2.0-pro-exp",
    "models/gemini-2.5-pro-preview-03-25",
    "models/gemini-2.5-pro-preview-05-06",
    "models/gemini-2.5-pro-preview-06-05",
    "models/gemini-2.5-flash-lite",
    "models/gemini-2.5-flash-image",
    "models/gemini-3-pro-preview",
    "models/gemini-flash-latest",
    "models/gemini-pro-latest",
]

successful = []
unsuccessful = []

for model_name in models_to_test:
    try:
        model = genai.GenerativeModel(model_name)
        # Try a minimal prompt to check quota
        response = model.generate_content("Hello, are you working?")
        if response and hasattr(response, "text"):
            print(f"✅ {model_name} - Success")
            successful.append(model_name)
        else:
            print(f"❌ {model_name} - No valid response")
            unsuccessful.append(model_name)
    except Exception as e:
        print(f"❌ {model_name} - Failed: {e}")
        unsuccessful.append(model_name)

print("\n=== Successful Models ===")
for m in successful:
    print(m)

print("\n=== Unsuccessful Models ===")
for m in unsuccessful:
    print(m)