from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=5009, log_level="info", reload=True)