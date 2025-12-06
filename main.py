from dotenv import load_dotenv

load_dotenv()

from app import app

# Note: The 'app' variable is automatically detected by Vercel as an ASGI application
