from datetime import datetime
import re
from bson import ObjectId
from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from project.others import (
    APP_ROOT,
    getRatingsByProdId,
    login_required,
    mergeUserAndCustomer,
    parse_json,
    removeCartSession,
    start_session,
    checkProdIdinSession,
    updateCartSession,
    OrderStatus,
)
from project import db


default = Blueprint("default", __name__)


@default.route("/is-user-email-exist", methods=["GET"])
def is_user_email_exist():
    email = request.args.get("email")
    user = db.users.find_one({"email": email})
    if user:
        return jsonify(False)
    else:
        return jsonify(True)


@default.route("/")
@default.route("/home/")
def home():
    categories = db.categories.find({"status": True})
    return render_template("/user/index.html", categories=categories)


# user - registration
@default.route("/register/", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        values = {
            "email": request.form.get("email"),
            "password": request.form.get("password"),
            "role": "customer",
            "status": True,
        }
        result = db.users.insert_one(values)
        userId = result.inserted_id
        user = db.users.find_one({"_id": ObjectId(userId)})
        start_session(user)
        flash("Registered Successfully", "success")
        return redirect(url_for("default.user_profile"))

    return render_template("/user/register.html")


@default.route("/login/", methods=["GET", "POST"])
def login():
    msg = ""
    if request.method == "POST":
        values = {
            "email": request.form.get("email"),
            "password": request.form.get("password"),
            "role": "customer",
        }
        user = db.users.find_one(values)
        if user:
            if user["is_active"]:
                start_session(user)
                # redirect to profile if not updated
                if user["address"] == "":
                    return redirect(url_for("default.user_profile"))

                return redirect(url_for("default.home"))
            else:
                msg = "Your login has been disabled"
        else:
            msg = "Invalid login credentials"
    return render_template("/user/login.html", msg=msg)


@default.route("/profile/", methods=["GET"])
def user_profile():
    userId = session["user"]["_id"]["$oid"]
    customer = db.users.find_one({"_id": ObjectId(userId)})
    return render_template("/user/profile.html", customer=customer)


@default.route("/profile/", methods=["POST"])
def user_profile_save():
    user_id = request.form.get("customerId")
    values = {
        "full_name": request.form.get("full_name"),
        "mobile_no": request.form.get("mobile_no"),
        "address": request.form.get("address"),
        "is_active": True,
        "status": True,
    }

    result = db.users.update_one({"_id": ObjectId(user_id)}, {"$set": values})
    user = db.users.find_one({"_id": ObjectId(user_id)})
    start_session(user)
    flash("Profile updated successfully", "success")
    return redirect(url_for("default.home"))


@default.route("/change-password", methods=["GET", "POST"])
def change_pasword():
    if request.method == "POST":
        id = session["user"]["_id"]["$oid"]
        password = request.form.get("password")
        result = db.users.update_one(
            {"_id": ObjectId(id)}, {"$set": {"password": password}}
        )
        if result.modified_count > 0:
            flash("Password Updated successfully", "success")
        else:
            flash("Error Updating Password", "danger")
        return redirect(url_for("default.change_pasword"))

    return render_template("/user/change_password.html")


@default.route("/sub-categories/")
def user_sub_categories():
    category_id = request.args.get("cid")
    category = db.categories.find_one({"_id": ObjectId(category_id), "status": True})

    if not category:
        return abort(404, "category not found")

    sub_categories = db.sub_categories.find(
        {"category_id": ObjectId(category_id), "status": True}
    )
    if not sub_categories:
        return abort(404, "sub_categories not found")

    return render_template(
        "/user/subcategories.html", category=category, sub_categories=sub_categories
    )


@default.route("/products/")
def user_products():
    # del session['cart']

    filter = {"status": True, "is_available": True}
    search_query = request.args.get("q")
    if search_query:
        rgx = re.compile(".*" + search_query + ".*", re.IGNORECASE)
        filter["product_title"] = rgx
    else:
        sub_category_id = request.args.get("scid")
        filter["sub_category_id"] = ObjectId(sub_category_id)

    products = db.products.find(filter)
    products = list(products)

    # for side menu in product page
    categories = db.categories.aggregate(
        [
            {"$match": {"status": True}},
            {
                "$lookup": {
                    "from": db.sub_categories.name,
                    "localField": "_id",
                    "foreignField": "category_id",
                    "pipeline": [
                        {"$match": {"status": True}},
                        {"$project": {"name": 1}},
                    ],
                    "as": "sub_category",
                }
            },
            {"$project": {"name": 1, "sub_category": 1}},
        ]
    )
    categories = list(categories)
    return render_template(
        "/user/products.html",
        products=products,
        categories=categories,
        isIdInSession=checkProdIdinSession,
        getProdRatings=getRatingsByProdId,
    )


# add product to cart
@default.route("/products/", methods=["POST"])
@default.route("/view-product/", methods=["POST"])
def add_product_cart():
    url = request.url
    product_id = request.form.get("product_id")
    quantity = int(request.form.get("quantity"))
    if not isinstance(quantity, int):
        flash("Quantity should be a whole number", "warning")
        return redirect(url)
    updateCartSession(product_id, quantity)
    return redirect(url)


# view product details
@default.route("/view-product/")
def view_product():
    product_id = request.args.get("pid")
    # product = db.products.find_one({"_id":product_id})
    product = db.products.aggregate(
        [
            {"$match": {"_id": ObjectId(product_id)}},
            {
                "$lookup": {
                    "from": db.reviews.name,
                    "localField": "_id",
                    "foreignField": "product_id",
                    "pipeline": [
                        {
                            "$lookup": {
                                "from": db.users.name,
                                "localField": "user_id",
                                "foreignField": "_id",
                                "as": "user",
                            }
                        },
                        {"$sort": {"_id": -1}},
                        {"$unwind": "$user"},
                    ],
                    "as": "reviews"
                }
            }
        ]
    )
    if not product:
        return abort(404, "Product Not Found")

    product = list(product)
    return render_template(
        "/user/view-product.html",
        product=product[0],
        isIdInSession=checkProdIdinSession,
    )


# cart
@default.route("/cart/")
@login_required
def cart():
    if "cart" not in session:
        flash("your cart is empty", "warning")
        return redirect(url_for("default.home"))

    if "delivery" not in session:
        session["delivery"] = True

    # get charges
    charges = db.charges.find_one()
    deliverChrg = float(charges["delivery"])
    taxPercentage = float(charges["tax"])

    amount: float = 0.0
    itemsTotalAmt: float = 0.0

    cart = []

    for item in session["cart"]:
        product = db.products.find_one({"_id": ObjectId(item["product_id"])})
        product["quantity"] = item["quantity"]
        amount = int(item["quantity"]) * float(product["price"])
        product["amount"] = amount
        itemsTotalAmt = itemsTotalAmt + amount
        cart.append(product)

    taxAmount = itemsTotalAmt * (taxPercentage / 100)
    orderAmount = itemsTotalAmt + taxAmount

    if session["delivery"]:
        orderAmount = orderAmount + deliverChrg

    months = [
        "JAN",
        "FEB",
        "MAR",
        "APR",
        "MAY",
        "JUN",
        "JUL",
        "AUG",
        "SEP",
        "OCT",
        "NOV",
        "DEC",
    ]
    years = [
        "2024",
        "2025",
        "2026",
        "2027",
        "2028",
        "2029",
        "2030",
        "2031",
        "2032",
        "2033",
        "2034",
    ]

    return render_template(
        "/user/cart.html",
        cart=cart,
        itemsTotalAmt=round(itemsTotalAmt, 2),
        deliveryCharge=round(deliverChrg, 2),
        orderAmount=round(orderAmount, 2),
        taxAmount=round(taxAmount, 2),
        taxPercentage=round(taxPercentage, 2),
        months=months,
        years=years,
    )


# update cart quantity from cart page
@default.route("/cart/update/", methods=["POST"])
def updateQtyToCart():
    product_id = request.form.get("product_id")
    quantity = request.form.get("quantity")
    updateCartSession(product_id, quantity)
    flash("Quantity updated successfully", "success")
    return redirect(url_for("default.cart"))


@default.route("/remove-item-cart/<id>/")
def removeItemFromCart(id):
    removeCartSession(id)
    flash("Item removed from cart", "success")
    return redirect(url_for("default.cart"))


# update delivery session value
@default.route("/update-delivery-session/", methods=["POST"])
def user_update_delivery_session():
    session["delivery"] = not bool(session["delivery"])
    return jsonify(True)


# add orders data
@default.route("/checkout/", methods=["POST"])
def user_checkout():
    user_id = session["user"]["_id"]["$oid"]

    orderType = request.form.get("orderType")
    deliveryAddress = request.form.get("deliveryAddress")
    itemsTotalAmt = request.form.get("itemsTotalAmt")
    orderDateTime = datetime.utcnow()
    orderAmount = request.form.get("orderAmount")

    order_values = {
        "user_id": ObjectId(user_id),
        "order_date_time": orderDateTime,
        "order_type": orderType,
        "items_total_amt": float(itemsTotalAmt),
        "order_amount": float(orderAmount),
        "order_status": OrderStatus.PENDING.value,
    }

    if orderType == "Delivery":
        order_values["delivery_address"] = deliveryAddress

    result = db.orders.insert_one(order_values)
    order_id = result.inserted_id

    # insert ordered items
    product_ids = request.form.getlist("product_id")
    prices = request.form.getlist("price")
    quantities = request.form.getlist("quantity")
    amounts = request.form.getlist("amount")

    for i, product_id in enumerate(product_ids):
        ordered_items = {
            "order_id": ObjectId(order_id),
            "product_id": ObjectId(product_id),
            "price": float(prices[i]),
            "quantity": int(quantities[i]),
            "amount": float(amounts[i]),
        }

        db.ordered_products.insert_one(ordered_items)

    # insert payment details
    deliveryCharge = request.form.get("deliveryCharge")
    taxAmount = request.form.get("taxAmount")
    taxPercentage = request.form.get("taxPercentage")
    card_details = {
        "card_holder_name": request.form.get("cardHolderName"),
        "card_number": request.form.get("cardNumber"),
        "exp_month": request.form.get("expMonth"),
        "exp_year": request.form.get("expYear"),
        "cvv": request.form.get("cvv"),
    }

    payment_values = {
        "order_id": ObjectId(order_id),
        "user_id": ObjectId(user_id),
        "items_total_amt": float(itemsTotalAmt),
        "tax_percentage": float(taxPercentage),
        "tax_amount": float(taxAmount),
        "order_amount": float(orderAmount),
        "payment_type": "Card",
        "card_details": card_details,
        "payment_status": "Paid",
    }

    if orderType == "Delivery":
        payment_values["delivery_charge"] = float(deliveryCharge)
    db.payments.insert_one(payment_values)

    del session["cart"]
    flash("Order Placed Successfully", "success")
    return redirect(url_for("default.user_ongoing_orders"))


# user - ongoing orders
@default.route("/ongoing-order/")
def user_ongoing_orders():
    user_id = session["user"]["_id"]["$oid"]
    orders = db.orders.aggregate(
        [
            {
                "$match": {
                    "user_id": ObjectId(user_id),
                    "order_status": {
                        "$nin": [
                            OrderStatus.DELIVERED.value,
                            OrderStatus.PICKED_UP.value,
                            OrderStatus.CANCELLED.value,
                        ]
                    },
                }
            },
            {"$sort": {"order_date_time": -1}},
            {
                "$lookup": {
                    "from": str(db.payments.name),
                    "localField": "_id",
                    "foreignField": "order_id",
                    "as": "payment",
                }
            },
        ]
    )
    return render_template(
        "/user/ongoing_orders.html", orders=orders, OrderStatus=OrderStatus
    )


@default.route("/orders/")
def user_orders():
    user_id = session["user"]["_id"]["$oid"]
    orders = db.orders.aggregate(
        [
            {"$match": {"user_id": ObjectId(user_id)}},
            {"$sort": {"order_date_time": -1}},
            {
                "$lookup": {
                    "from": str(db.payments.name),
                    "localField": "_id",
                    "foreignField": "order_id",
                    "as": "payment",
                }
            },
        ]
    )
    return render_template("/user/orders.html", orders=orders, OrderStatus=OrderStatus)


# user order details
@default.route("/order-details/<oid>")
def user_order_details(oid):
    orderId = ObjectId(oid)
    order = db.orders.aggregate(
        [
            {"$match": {"_id": orderId}},
            {
                "$lookup": {
                    "from": str(db.payments.name),
                    "localField": "_id",
                    "foreignField": "order_id",
                    "as": "payment",
                }
            },
        ]
    )

    order = list(order)
    orderedItems = db.ordered_products.aggregate(
        [
            {"$match": {"order_id": orderId}},
            {
                "$lookup": {
                    "from": str(db.products.name),
                    "localField": "product_id",
                    "foreignField": "_id",
                    "as": "product",
                }
            },
        ]
    )
    return render_template(
        "/user/order_details.html",
        order=order[0],
        orderedItems=orderedItems,
        OrderStatus=OrderStatus,
    )


# user - cancel order
@default.route("/cancel-order/<oid>/")
def user_cancel_order(oid):
    order_id = ObjectId(oid)
    order = db.orders.find_one({"_id": order_id})
    if not order:
        return abort(404, "Order Not Found")

    # get cancellation charges from charges collection
    charges = db.charges.find_one({})
    cancellation_percentage = float(charges["cancellation"])
    cancellation_charge = round(
        float(order["order_amount"]) * (cancellation_percentage / 100), 2
    )
    refund_amount = float(order["order_amount"]) - cancellation_charge

    # update payment collection
    db.payments.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "payment_status": "Refunded",
                "cancellation_percentage": cancellation_percentage,
                "cancellation_charge": cancellation_charge,
                "refund_amount": refund_amount,
            }
        },
    )

    db.orders.update_one(
        {"_id": order_id}, {"$set": {"order_status": OrderStatus.CANCELLED.value}}
    )
    flash("This order has been cancelled successfully", "success")

    return redirect(url_for("default.user_order_details", oid=oid))


# user add / update product review
@default.route("/product-review/", methods=["POST"])
def user_update_product_review():
    user_id = session["user"]["_id"]["$oid"]
    order_id = request.form.get("order_id")

    values = {
        "user_id": ObjectId(user_id),
        "order_id": ObjectId(order_id),
        "product_id": ObjectId(request.form.get("product_id")),
        "rating": int(request.form.get("rating")),
        "review": request.form.get("review"),
    }

    review_id = request.form.get("review_id")

    if not review_id:
        review_id = ObjectId()
        values["_id"] = review_id

    db.reviews.update_one({"_id": ObjectId(review_id)}, {"$set": values}, upsert=True)
    flash("Thank you for your valuable review", "success")

    return redirect(url_for("default.user_order_details", oid=order_id))


# user product review
@default.route("/get-product-review/")
def user_get_product_review():
    user_id = session["user"]["_id"]["$oid"]
    order_id = request.args.get("order_id")
    product_id = request.args.get("product_id")
    result = db.reviews.find_one(
        {
            "user_id": ObjectId(user_id),
            "order_id": ObjectId(order_id),
            "product_id": ObjectId(product_id),
        }
    )

    result = parse_json(result)
    return jsonify(result)


# ---------------------------------------------------------------------------------------------------------------


@default.route("/restaurant")
def add_restaurant():
    return render_template("/user/restaurant/restaurant.html")


@default.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("default.home"))
