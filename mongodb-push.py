import pymongo
from pymongo import MongoClient


mongo_client = pymongo.MongoClient('mongodb+srv://sahuansh286_db_user:oGqXeEDysKXz0pT6@cluster0.xhipcwh.mongodb.net/blinkit_scraper_db?retryWrites=true&w=majority')
db = mongo_client['blinkit_scraper_db']
input_table = db['Input_Blinkit_URLs']


data = [
    {
        "id": 1,
        "product_link": "https://blinkit.com/prn/fortune-soya-health-refined-soyabean-oil-870-g/prid/52",

    },
    {
        "id": 2,
        "product_link": "https://blinkit.com/prn/uncle-chipps-spicy-treat-flavour-potato-chips/prid/11150",

    },
    {
        "id": 3,
        "product_link": "https://blinkit.com/prn/lays-chile-limon-flavour-potato-chips/prid/574",

    },
]


# [3] Insert into MongoDB (will add all documents, skip if already exists)
if data and isinstance(data, list):
    #  First delete existing documents
    input_table.delete_many({})
    insert_result = input_table.insert_many(data)
    print(f" Inserted {len(insert_result.inserted_ids)} documents into MongoDB collection.")
else:
    print(" No data to import or format error.")

# [4] Confirm import (show data count)
count = input_table.count_documents({})
print(f"📊 Now {count} documents total in Input_Blinkit_URLs.")

# [5] Print some sample docs for verification
for doc in input_table.find().limit(10):
    print(doc)
