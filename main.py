from dotenv import load_dotenv

load_dotenv()

from app import app  # noqa: E402, F401 - Vercel requires 'app' variable in this file

# Note: The 'app' variable is automatically detected by Vercel as an ASGI application
