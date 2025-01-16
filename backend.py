from fastapi import FastAPI
from pymongo import MongoClient
from bson import json_util

from main import process_harmonic_list

app = FastAPI()

# MongoDB connection setup
mongo_client = MongoClient("mongodb://admin:password@mongodb:27017/")
mongo_db = mongo_client["app"]
mongo_collection = mongo_db["final_data"]


@app.get("/data")
async def get_data():
    # Convert cursor to a list of documents
    data = list(mongo_collection.find())
    # Optionally serialize the documents into JSON
    serialized_data = json_util.dumps(data)
    return serialized_data


@app.post("/preprocess")
async def process_harmonic_list_route(list_urn: str):
    process_harmonic_list()
