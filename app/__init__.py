from fastapi import FastAPI
from pymongo import MongoClient
from mongoengine import connect
import os
import app.controllers.auth_controller as auth_controller
import app.controllers.movie_controller as movie_controller

app = FastAPI(title="Cinelog API",)

# Get MongoDB connection details from environment variables, with defaults for local development
mongodb_host = os.getenv("MONGODB_HOST", "localhost")
mongodb_port = int(os.getenv("MONGODB_PORT", "27017"))
mongodb_db = os.getenv("MONGODB_DB", "cinelog_db")

mongo_client = MongoClient(f"mongodb://{mongodb_host}:{mongodb_port}/{mongodb_db}")

connect(mongodb_db, host=mongodb_host, port=mongodb_port)

@app.get('/', tags=['Root'], summary="Cinelog API Root")
def index():
    return "Welcome to the Cinelog API!"


app.include_router(auth_controller.router, prefix='/v1/auth', tags=['Auth'])
app.include_router(movie_controller.router, prefix='/v1/movies', tags=['Movies'])

def create_app():
    return app