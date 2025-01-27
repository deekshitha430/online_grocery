import pathlib
from bson import ObjectId
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for

from project import db
from project.others import APP_ROOT, OrderStatus, generateUniqueId, getRatingsByMenuId, getRatingsByrestaurantId, login_required, start_session, parse_json


admin = Blueprint("admin", __name__)


@admin.route("/admin/", methods=['GET', 'POST'])
@admin.route("/admin/login/", methods=['GET', 'POST'])
def admin_login():
    msg = ""
    values = ""
    if request.method == "POST":
        values = {
            "user_name": request.form["user_name"],
            "password": request.form["password"]
        }

        user = db.admin.find_one(values)
        if not user:
            msg = "Invalid Login Credentials"
        else:
            start_session(user)
            return redirect(url_for("admin.admin_dashboard"))

    return render_template("/admin/login.html", msg=msg, values=values)


@admin.route("/admin/change-password", methods=['GET', 'POST'])
def admin_change_pasword():
    if request.method == 'POST':
        id = session['user']['_id']['$oid']
        password = request.form.get('password')
        result = db.admin.update_one({"_id": ObjectId(id)}, {
                                     "$set": {"password": password}})
        if result.modified_count > 0:
            flash("Password Updated successfully", "success")
        else:
            flash("Error Updating Password", "danger")
        return redirect(url_for("admin.admin_change_pasword"))

    return render_template("/admin/change_password.html")


@admin.route("/admin/logout/")
def admin_logout():
    session.clear()
    return redirect(url_for("admin.admin_login"))


@admin.route("/admin/dashboard/")
@login_required
def admin_dashboard():

    total_products = db.products.count_documents({"status":True})
    out_of_stock = db.products.count_documents({"status":True, "is_available":False})
    reg_users = db.users.count_documents({})
    total_orders = db.orders.count_documents({})
    completed_orders = db.orders.count_documents({"order_status":{"$in":[OrderStatus.PICKED_UP.value, OrderStatus.DELIVERED.value]}})
    cancelled_orders = db.orders.count_documents({"order_status":OrderStatus.CANCELLED.value})

    dashboard = {
        "total_products": total_products,
        "out_of_stock": out_of_stock,
        "reg_users": reg_users,
        "total_orders":total_orders,
        "completed_orders": completed_orders,
        "cancelled_orders": cancelled_orders        
    }

    return render_template("/admin/dashboard.html",  dashboard=dashboard)

@admin.route("/admin/categories/", methods=['GET', 'POST'])
@admin.route("/admin/edit-category/")
def admin_categories():
    category = ""
    if request.method == 'POST':
        category_id = request.form.get('category_id')
        name = request.form.get('name').title()
        image = request.files.get('image')
        if not category_id:
            # Add Category
            id = ObjectId()
            image = request.files.get('image')
            extension = pathlib.Path(image.filename).suffix
            img_file_name = str(id) + extension

            db.categories.insert_one({"_id":id, "name": name, "img_file_name":img_file_name, "status":True})
            image.save(APP_ROOT+"/images/uploads/categories/"+img_file_name)
            flash("Category added successfully", "success")
        else:
            # Update Category
            img_file_name = request.form.get('img_file_name')
            if image.filename:
                extension = pathlib.Path(image.filename).suffix
                img_file_name = str(category_id) + extension
            result = db.categories.update_one(
                {"_id": ObjectId(category_id)}, {"$set": {"name": name, "img_file_name":img_file_name}})
            if result.modified_count > 0:
                if image.filename:
                    image.save(
                        APP_ROOT+"/images/uploads/categories/"+img_file_name)
                flash("Category name updated successfully", "success")
            else:
                flash("No changes made", "warning")

        return redirect(url_for("admin.admin_categories"))

    # Edit Category
    if request.args.get('id'):
        category = db.categories.find_one({"_id": ObjectId(request.args.get('id'))})

    categories = db.categories.find({"status": True})
    return render_template("/admin/categories.html", categories=categories, category=category)


@admin.route("/admin/delete-category/")
def admin_delete_category():
    category_id = request.args.get('id')
    db.categories.update_one({"_id":ObjectId(category_id)},{"$set":{"status":False}})
    db.sub_categories.update_many({"category_id":ObjectId(category_id)},{"$set":{"status":False}})
    db.products.update_many({"category_id":ObjectId(category_id)},{"$set":{"status":False}})

    flash("Category Deleted Successfully", "success")

    return redirect(url_for("admin.admin_categories"))


@admin.route("/admin/sub-categories/", methods=['GET', 'POST'])
@admin.route("/admin/edit-sub-category/")
def admin_subcategories():
    sub_category = ""
    if request.method == 'POST':
        sub_category_id = request.form.get('sub_category_id')
        category_id = request.form.get('category_id')
        name = request.form.get('name').title()
        image = request.files.get('image')
        if not sub_category_id:
            # Add Sub Category
            id = ObjectId()
            image = request.files.get('image')
            extension = pathlib.Path(image.filename).suffix
            img_file_name = str(id) + extension

            db.sub_categories.insert_one({"_id":id, "category_id":ObjectId(category_id), "name": name, "img_file_name":img_file_name, "status":True})
            image.save(APP_ROOT+"/images/uploads/sub_categories/"+img_file_name)
            flash("Sub Category added successfully", "success")
        else:
            # Update Category
            img_file_name = request.form.get('img_file_name')
            if image.filename:
                extension = pathlib.Path(image.filename).suffix
                img_file_name = str(sub_category_id) + extension
            result = db.sub_categories.update_one(
                {"_id": ObjectId(sub_category_id)}, {"$set": {"name": name, "img_file_name":img_file_name}})
            if result.modified_count > 0:
                if image.filename:
                    image.save(
                        APP_ROOT+"/images/uploads/sub_categories/"+img_file_name)
                flash("Sub Category name updated successfully", "success")
            else:
                flash("No changes made", "warning")

        return redirect(url_for("admin.admin_subcategories", cid=category_id))    


    # get category details
    category_id = request.args.get("cid")
    category = db.categories.find_one({"_id":ObjectId(category_id),"status": True})
    if not category:
        return abort(404, "Category not found")

    # get all subcategories by category id
    sub_categories = db.sub_categories.aggregate([
            {"$match":{"category_id":ObjectId(category_id),"status":True}},
            {
                "$lookup": {
                    "from": db.categories.name,
                    "localField": "category_id",
                    "foreignField": "_id",
                    "as": "category"
                }
            }
        ])
    
    # Edit SUb Category
    scid = request.args.get('scid')
    if scid:
        sub_category = db.sub_categories.find_one({"_id":ObjectId(scid)})

    return render_template("/admin/sub-categories.html", category=category, sub_categories=sub_categories, sub_category=sub_category)


# admin - delete sub category
@admin.route("/admin/delete-sub-category/")
def admin_delete_sub_category():
    sub_category_id = request.args.get("scid")
    category_id = request.args.get("cid")
    db.sub_categories.update_one({"_id":ObjectId(sub_category_id)}, {"$set":{"status":False}})
    db.products.update_many({"sub_category_id":ObjectId(sub_category_id)}, {"$set":{"status":False}})
    flash("Sub Category deleted successfully", "success")
    return redirect(url_for("admin.admin_subcategories", cid=category_id))


# add / update charges
@admin.route("/admin/charges/", methods=['GET','POST'])
@admin.route("/admin/edit-charge/")
def admin_charges():
    if request.method == "POST":
        charge_id = request.form.get("charge_id")

        values = {
            "delivery":request.form.get("delivery"),
            "tax":request.form.get("tax"),
            "cancellation":request.form.get("cancellation"),
        }

        if not charge_id:
            # add charges
            result = db.charges.insert_one(values)
            if result.inserted_id:
                flash("charges added successfully", "success")
        else:
            # update charges
            result = db.charges.update_one({"_id":ObjectId(charge_id)}, {"$set":values})
            if result.modified_count > 0:
                flash("charges updated successfully", "success")
        return redirect(url_for("admin.admin_charges"))

    

    # get all charges
    charge = db.charges.find_one({})
    return render_template("/admin/charges.html", charge=charge)


# view products
@admin.route("/admin/products/")
def admin_products():
    filter = {"status":True}

    
    if request.args.get("is-available"):
        filter["is_available"] = True if request.args.get("is-available") == '1' else False
    
    
    products = db.products.aggregate([
        {"$match":filter},
        {
            "$lookup":{
                "from": db.categories.name,
                "localField": "category_id",
                "foreignField": "_id",
                "pipeline":[
                    {"$project":{"name":1}}
                ],
                "as": "category"
            }
        },
        {
            "$lookup":{
                "from": db.sub_categories.name,
                "localField": "sub_category_id",
                "foreignField": "_id",
                "pipeline":[
                    {"$project":{"name":1}}
                ],
                "as": "sub_category"
            }
        },
        {"$sort": {"is_available": 1}},
    ])
    products=list(products)
    list.reverse(products)
    return render_template("/admin/products.html", products=products)


# save product
@admin.route("/admin/product/", methods=['GET','POST'])
@admin.route("/admin/edit-product/")
def admin_save_product():
    if request.method == 'POST':
        product_id = request.form.get("product_id")
        form_data = {
            "category_id":ObjectId(request.form.get("category_id")),
            "sub_category_id":ObjectId(request.form.get("sub_category_id")),
            "brand_name":request.form.get("brand_name"),
            "product_title":request.form.get("product_title"),
            "mrp": float(request.form.get("mrp")),
            "price": float(request.form.get("price")),
            "description": request.form.get("description"),
            "is_returnable":True if request.form.get("is_returnable") else False,
            "is_available":True
        }
        image = request.files.get("product_image")
        if not product_id:
            # add product
            id = ObjectId()
            form_data["_id"] = id
            form_data["status"] = True
            if image.filename:
                extension = pathlib.Path(image.filename).suffix
                img_file_name = str(id) + extension
                form_data["img_file_name"] = img_file_name

            result = db.products.insert_one(form_data)
            if result.inserted_id:
                image.save(APP_ROOT+"/images/uploads/products/"+img_file_name)
                flash("Product added successfully", "success")
        else:
            # update product
            img_file_name = request.form.get("img_file_name")
            if image.filename:
                extension = pathlib.Path(image.filename).suffix
                img_file_name = str(product_id) + extension
            form_data["img_file_name"] = img_file_name
            result = db.products.update_one({"_id":ObjectId(product_id)}, {"$set":form_data})
            if image.filename:
                image.save(APP_ROOT+"/images/uploads/products/"+img_file_name)
                flash("Product updated successfully", "success")
        return redirect(url_for("admin.admin_products"))

    categories = db.categories.find({"status":True})
    # edit product
    product = ""
    product_id = request.args.get("pid")
    if product_id:
        product = db.products.find_one({"_id":ObjectId(product_id), "status":True})        
        if not product:
            return abort(404, 'Product Not Found')
        product["sub_category"] = db.sub_categories.find({"category_id":ObjectId(product['category_id'])},{"name":1})
    return render_template("/admin/product-save.html", categories=categories, product=product)


# ajax get sub category by category
@admin.route("/admin/get-sub-category/")
def admin_get_subcategory_by_category():
    category_id = request.args.get("category_id")
    sub_categories = db.sub_categories.find({"category_id":ObjectId(category_id), "status":True},{"name":1})
    if sub_categories:
        return parse_json(sub_categories)
    
    return jsonify(False)


# update product availability status
@admin.route("/admin/product-availability-update/")
def admin_set_product_availability():
    product_id = request.args.get("pid")
    product = db.products.find_one({"_id":ObjectId(product_id)})
    if not product:
        return abort(404, "Product not available")
    is_available = not product['is_available']
    result = db.products.update_one({"_id":ObjectId(product_id)}, {"$set":{"is_available":is_available}})
    if result.modified_count > 0:
        flash("Availability updated successfully", "success")
    else:
        flash("Error updating availability status", "danger")
    return redirect(url_for("admin.admin_products"))


# admin - view product
@admin.route("/admin/view-product/<pid>/")
def admin_view_product(pid):
    product_id = ObjectId(pid)
    product = db.products.aggregate([
        {"$match":{"_id":product_id}},
        {
            "$lookup":{
                "from": db.reviews.name,
                "localField": "_id",
                "foreignField": "product_id",
                "pipeline":[
                    {
                        "$lookup":{
                            "from":db.users.name,
                            "localField": "user_id",
                            "foreignField": "_id",
                            "as":"user"
                        }
                    },
                    {"$unwind":"$user"}
                ],
                "as": "reviews"
            }  
        }
    ])
    product = list(product)

    return render_template("/admin/product-view.html", product=product[0])


# admin - delete product
@admin.route("/admin/delete-product/<pid>/")
def admin_delete_product(pid):
    product_id = ObjectId(pid)
    result = db.products.update_one({"_id":product_id},{"$set":{"status":False}})
    if result.modified_count > 0:
        flash("Product deleted successfully", "success")
    else:
        flash("Error deleting product", "danger")
    return redirect(url_for("admin.admin_products"))

# admin - view orders
@admin.route("/admin/orders/")
def admin_view_orders():
    order_type = request.args.get('order-type')
    order_status = request.args.get('order-status')

    filter = {}
    if order_type:
        filter["order_type"] = order_type
        filter["order_status"] = {"$nin": [OrderStatus.DELIVERED.value, OrderStatus.PICKED_UP.value, OrderStatus.CANCELLED.value]}

    if order_status:
        filter["order_status"] = int(order_status)
        
    orders = db.orders.aggregate([
        {"$match": filter},
        {"$sort": {"order_date_time": -1}},
        {
            "$lookup": {
                "from": db.payments.name,
                "localField": "_id",
                "foreignField": "order_id",
                "as": "payment"
            }
        }
    ])

    count_filter = {
        "order_status": {"$nin": [OrderStatus.DELIVERED.value, OrderStatus.PICKED_UP.value, OrderStatus.CANCELLED.value]}
    }
    count_filter["order_type"] = "Delivery"
    deliveryCount = db.orders.count_documents(count_filter)

    count_filter["order_type"] = "Pickup"
    pickupCount = db.orders.count_documents(count_filter)

    return render_template("/admin/orders.html", orders=orders, deliveryCount=deliveryCount, pickupCount=pickupCount, OrderStatus=OrderStatus)


# admin order details
@admin.route("/admin/order-details/<oid>")
def admin_order_details(oid):
   orderId = ObjectId(oid)
   order = db.orders.aggregate([
      {"$match": {"_id": orderId}},
      {
         "$lookup": {
            "from": str(db.payments.name),
            "localField": "_id",
            "foreignField": "order_id",
            "as": "payment"
            }
      },
      {
         "$lookup": {
            "from": str(db.users.name),
            "localField": "user_id",
            "foreignField": "_id",
            "as": "user"
            }
      }
      ])
   
   order = list(order)
   orderedItems = db.ordered_products.aggregate([
        {
            "$match": {"order_id": orderId}
        },
        {
            "$lookup": {
                "from": str(db.products.name),
                "localField": "product_id",
                "foreignField": "_id",
                "as": "product"
            }
        }
   ])
   return render_template("/admin/order-details.html", order=order[0], orderedItems=orderedItems, OrderStatus=OrderStatus, str=str)

# update order status
@admin.route("/admin/update-order-status/" , methods=['POST'])
def admin_update_order_status():
    oid = request.form.get("order_id")
    status = int(request.form.get("status"))

    db.orders.update_one({"_id":ObjectId(oid)}, {"$set":{"order_status":status}})
    flash("Status updated", "success")
    return jsonify(True)

# view menu ratings and reviews
@admin.route("/restaurant/food/reviews/<menuId>/<restaurantId>")
def admin_view_food_reviews(menuId, restaurantId):
    menu = db.menus.find_one({"_id": ObjectId(menuId)})

    if not menu:
        return abort(404, "Menu Not Found")

    reviews = db.foodReviews.aggregate([
        {"$match": {"menuId": ObjectId(menuId)}},
        {
            "$lookup": {
                "from": db.customers.name,
                "localField": "customerId",
                "foreignField": "_id",
                "as": "customer"
            }
        }
    ])

    reviews = list(reviews)
    list.reverse(reviews)

    ratings = getRatingsByMenuId(menuId)
    return render_template("/admin/food_reviews.html", ratings=ratings, menu=menu, reviews=reviews, restaurantId=restaurantId)


# View registered users
@admin.route("/admin/users/")
def admin_users():
    users = db.users.find({}).sort("is_active", -1)
    return render_template("/admin/users.html", users=users)


# Update Users active Status
@admin.route("/admin/user/update-active-status/<userId>/")
def admin_update_user_status(userId):
    user = db.users.find_one({"_id": ObjectId(userId)})
    if user:
        status = not user['is_active']
        db.users.update_one({"_id": ObjectId(userId)}, {
                            "$set": {"is_active": status}})
        flash("User status updated successfully", "success")

    return redirect(url_for("admin.admin_users"))


@admin.route("/admin/transactions/")
def admin_transactions():
    transactions = db.orders.aggregate([
        {"$match": {"order_status": {"$in": [OrderStatus.DELIVERED.value, OrderStatus.PICKED_UP.value, OrderStatus.CANCELLED.value]}}},
        {
            "$lookup": {
                "from": db.payments.name,  # collection name
                "localField": "_id",  # field in categories table
                "foreignField": "order_id",  # field in Menus table
                "as": "payment_list"
            }
        },
        {
            "$sort": {"orderDateTime": -1}
        }
    ])

    transactions = list(transactions)
    list.reverse(transactions)
    return render_template("/admin/transactions.html", transactions=transactions, float=float)
