from flask import Flask
from flask_pymongo import PyMongo
from dotenv import load_dotenv
from mongoengine import connect
from app.controllers.auth_controller import auth_controller

load_dotenv(
    dotenv_path='../.env'
)

app = Flask(__name__)

# Configure Flask-PyMongo
app.config["MONGO_URI"] = "mongodb://localhost:27017/cinelog_db"
mongo = PyMongo(app)

# Configure MongoEngine
connect('cinelog_db', host='localhost', port=27017)

@app.route('/')
def index():
    return "Welcome to the Cinelog API!"

# Blueprints
app.register_blueprint(auth_controller, url_prefix='/v1/auth')

def create_app():
    return app