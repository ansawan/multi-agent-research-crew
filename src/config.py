import os
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini/gemini-2.5-flash")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
API_KEY = os.getenv("API_KEY", "")
N8N_DELIVERY_WEBHOOK_URL = os.getenv("N8N_DELIVERY_WEBHOOK_URL", "")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

def validate_config(raise_error=False):
    """
    Validates essential configuration settings.
    Returns (is_valid, message) with bilingual Roman Urdu + English explanation.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY.strip() == "" or GEMINI_API_KEY == "your_gemini_api_key_here":
        msg = (
            "\n❌ CONFIGURATION ERROR / SETTING MISSING!\n"
            "Urdu: .env file mein GEMINI_API_KEY maujood nahi hai ya placeholder hai.\n"
            "      Kripya https://aistudio.google.com/apikey se key le kar .env mein paste karen.\n"
            "English: GEMINI_API_KEY is missing or invalid in your .env file.\n"
            "         Please obtain a free key at https://aistudio.google.com/apikey and update .env.\n"
        )
        if raise_error:
            raise ValueError(msg)
        return False, msg
    return True, "Configuration valid!"
