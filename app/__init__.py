from fastapi import FastAPI
from pymongo import MongoClient
from dotenv import load_dotenv
from mongoengine import connect
import app.controllers.auth_controller as auth_controller
import app.controllers.movie_controller as movie_controller
from pathlib import Path

dotenv_pah = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_pah)

app = FastAPI(title="Cinelog API",)

mongo_client = MongoClient("mongodb://localhost:27017/cinelog_db")

connect('cinelog_db', host='localhost', port=27017)

@app.get('/', tags=['Root'], summary="Cinelog API Root")
def index():
    return "Welcome to the Cinelog API!"


app.include_router(auth_controller.router, prefix='/v1/auth', tags=['Auth'])
app.include_router(movie_controller.router, prefix='/v1/movies', tags=['Movies'])

def create_app():
    return app