from bson import ObjectId
import pymongo

dbClient = pymongo.MongoClient('mongodb://localhost:27017/')
db = dbClient["grocery"]

admin = db['admin']
categories = db['categories']
sub_categories = db['sub_categories']
charges = db['charges']
products = db['products']
users = db['users']
orders = db['orders']
ordered_products= db['ordered_products']
payments = db['payments']
reviews = db['reviews']

# def getCityById(id):
#   return cities.find_one({"_id":ObjectId(id)})

# def getMenuById(id):
#   return menus.find_one({"_id":ObjectId(id)})