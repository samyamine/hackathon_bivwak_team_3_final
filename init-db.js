// Create a default collection and insert a document
db = db.getSiblingDB('app'); 
db.createCollection('final_data'); 
db.final_data.createIndex({ id: 1 }, { unique: true });