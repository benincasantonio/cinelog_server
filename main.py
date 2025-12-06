from dotenv import load_dotenv

load_dotenv()

from app import app

handler = app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=5009, log_level="info", reload=True)
