from dotenv import load_dotenv

load_dotenv()

from app import app as app  # noqa: E402, F401


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=5009, reload=True)
