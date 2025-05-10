from flask import Flask
from flask_pymongo import PyMongo

app = Flask(__name__)

# Configurazione del database MongoDB
app.config["MONGO_URI"] = "mongodb://localhost:27017/cinelog_db"
mongo = PyMongo(app)

@app.route('/')
def index():
    return "Welcome to the Cinelog API!"

def create_app():
    return app