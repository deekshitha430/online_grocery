from datetime import datetime
from enum import Enum
from functools import wraps
import json
from flask import abort, redirect, session, url_for
from bson import ObjectId, json_util
import os

from project import db

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = APP_ROOT + "/static"


def parse_json(data):
    return json.loads(json_util.dumps(data))

# Get ratings and number of ratings of restaurant


def getRatingsByrestaurantId(id):
    restaurantId = int(id)
    ratings = db.restaurantReviews.aggregate([
        {"$match": {"restaurantId": restaurantId}},
        {
            "$group": {
                "_id": "null",
                "totalRatings": {"$sum": "$rating"},
                "count": {"$sum": 1}
            }
        }
    ])
    ratings = list(ratings)

    if ratings:
        restRatings = round(
            int(ratings[0]['totalRatings']) / int(ratings[0]['count']), 1)
        return {"restaurantRatings": restRatings, "countOfRatings": ratings[0]['count']}
    else:
        return {"restaurantRatings": 0, "countOfRatings": 0}


# Get ratings and number of ratings of food items
def getRatingsByMenuId(id):
    menuId = ObjectId(id)
    ratings = db.foodReviews.aggregate([
        {"$match": {"menuId": menuId}},
        {
            "$group": {
                "_id": "null",
                "totalRatings": {"$sum": "$rating"},
                "count": {"$sum": 1}
            }
        }
    ])
    ratings = list(ratings)

    if ratings:
        restRatings = round(
            int(ratings[0]['totalRatings']) / int(ratings[0]['count']), 1)
        return {"menuRatings": restRatings, "countOfRatings": ratings[0]['count']}
    else:
        return {"menuRatings": 0, "countOfRatings": 0}
    

# Get ratings and number of ratings of product
def getRatingsByProdId(id):
    product_id = ObjectId(id)
    ratings = db.reviews.aggregate([
        {"$match": {"product_id": product_id}},
        {
            "$group": {
                "_id": "null",
                "totalRatings": {"$sum": "$rating"},
                "count": {"$sum": 1}
            }
        }
    ])
    ratings = list(ratings)

    if ratings:
        prodRatings = round(
            int(ratings[0]['totalRatings']) / int(ratings[0]['count']), 1)
        return {"prodRatings": prodRatings, "countOfRatings": ratings[0]['count']}
    else:
        return {"prodRatings": 0, "countOfRatings": 0}

# add / update product to cart
def updateCartSession(product_id, quantity):
    cart = []
    if 'cart' in session:
        cart = session['cart']
        itemExists = False
        for index, value in enumerate(cart):
            if value["product_id"] == product_id:
                cart[index]["quantity"] = quantity
                itemExists = True
                break  # exit the for loop
        if not itemExists:
            cart.append({'product_id': product_id, 'quantity': quantity})
    else:
        cart.append({'product_id': product_id, 'quantity': quantity})

    session["cart"] = cart

# remove product from cart
def removeCartSession(product_id):
    cart = []
    if 'cart' in session:
        cart = session['cart']
        itemExist = False
        for index, value in enumerate(cart):
            if value["product_id"] == product_id:
                del cart[index]
                itemExist = True
                break  # exit the for loop

    session["cart"] = cart


def checkProdIdinSession(product_id):
    isExist = False
    product_id = str(product_id)
    if 'cart' in session:
        for item in session['cart']:
            if product_id == item['product_id']:
                isExist = True
                break
    return isExist

def checkMenuIdinSession(menuId):
    isExist = False
    menuId = str(menuId)
    if 'cart' in session:
        for item in session['cart']:
            if menuId == item['menuId']:
                isExist = True
                break
    return isExist

#  Merge User and Customer Collection into single collection


def mergeUserAndCustomer(customerId):
    customer = db.customers.find_one({"_id": ObjectId(customerId)})
    user = db.users.find_one({"_id": ObjectId(customer['userId'])})
    customer['custId'] = customer['_id']
    del customer['_id']
    del customer['userId']
    user.update(customer)
    return user

# Session
def start_session(user):
    session['logged_in'] = True
    del user['password']
    # user['_id'] = str(user['_id'])
    session['user'] = parse_json(user)


# Decorators
def login_required(fn):
    @wraps(fn)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return fn(*args, **kwargs)
        else:
            return redirect("/login/")

    return wrap


def admin_only(fn):
    @wraps(fn)
    def wrap(*args, **kwargs):
        if session['user']['role'] == "Admin":
            return fn(*args, **kwargs)
        else:
            return abort(403, "You are not authorized to view this page")

    return wrap


def owner_only(fn):
    @wraps(fn)
    def wrap(*args, **kwargs):
        if session['user']['role'] == "restaurant":
            return fn(*args, **kwargs)
        else:
            return abort(403, "You are not authorized to view this page")

    return wrap


def user_only(fn):
    @wraps(fn)
    def wrap(*args, **kwargs):
        if 'role' in session:
            return fn(*args, **kwargs)
        else:
            return abort(403, "You are not authorized to view this page")

    return wrap


def generateUniqueId():
    now = datetime.now()
    dt = now.strftime("%Y%m%d%H%M%S")
    return dt


# order status enum
class OrderStatus(Enum):
    PENDING=1
    CONFIRMED=2
    PACKING=3
    READY=4
    OUT_FOR_DELIVERY=5
    DELIVERED=6
    READY_TO_PICKUP=7
    PICKED_UP=8
    CANCELLED=9
    
