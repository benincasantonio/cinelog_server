from fastapi import FastAPI
from pymongo import MongoClient
from dotenv import load_dotenv
from mongoengine import connect
import app.controllers.auth_controller as auth_controller

load_dotenv()

app = FastAPI(title="Cinelog API",)

mongo_client = MongoClient("mongodb://localhost:27017/cinelog_db")

connect('cinelog_db', host='localhost', port=27017)

@app.get('/', tags=['Root'], summary="Cinelog API Root")
def index():
    return "Welcome to the Cinelog API!"


app.include_router(auth_controller.router, prefix='/v1/auth', tags=['Auth'])

def create_app():
    return app