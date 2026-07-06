from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
print("Key loaded from GOOGLE_API_KEY starts with:", api_key[:10] if api_key else "None")

gemini_key = os.getenv("GEMINI_API_KEY")
print("Key loaded from GEMINI_API_KEY starts with:", gemini_key[:10] if gemini_key else "None")

# Use key from environment
client = genai.Client()
try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Hello"
    )
    print("Default Client Response:", response.text)
except Exception as e:
    print("Default Client Error:", str(e))

# Explicitly passing GOOGLE_API_KEY
if api_key:
    try:
        client_explicit = genai.Client(api_key=api_key)
        response_explicit = client_explicit.models.generate_content(
            model="gemini-2.5-flash",
            contents="Hello"
        )
        print("Explicit Client Response:", response_explicit.text)
    except Exception as e:
        print("Explicit Client Error:", str(e))
