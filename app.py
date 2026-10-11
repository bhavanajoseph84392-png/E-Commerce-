from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import mysql.connector
import bcrypt
import random
from datetime import datetime, timedelta
import smtplib
from email.message import EmailMessage
from werkzeug.utils import secure_filename
import os
import razorpay
app = Flask(__name__)
app.secret_key = "my-super-secret-key"
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["PRODUCT_UPLOAD_FOLDER"] = os.path.join(
    app.root_path,"static","products"
)

os.makedirs(app.config["PRODUCT_UPLOAD_FOLDER"],exist_ok=True)

RAZORPAY_KEY_ID = os.getenv(
    "RAZORPAY_KEY_ID",
    "rzp_test_TmW2ZmMAI2LMJv"
)

RAZORPAY_KEY_SECRET = os.getenv(
    "RAZORPAY_KEY_SECRET",
    "ja8RwWiCQT5vUX1N6OoEG70r"
)

RAZORPAY_PLACEHOLDER_SECRET = "PASTE_YOUR_RAZORPAY_TEST_SECRET_HERE"

if RAZORPAY_KEY_SECRET and RAZORPAY_KEY_SECRET != RAZORPAY_PLACEHOLDER_SECRET:
    razorpay_client = razorpay.Client(
        auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
    )
else:
    razorpay_client = None

ALLOWED_EXTENSIONS = {"png","jpg","jpeg","gif","webp"}
def allowed_file(filename):
    return ("." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )

ALLOWED_PRODUCT_EXTENSIONS = {"jpg","jpeg","png","gif","webp"}
def allowed_product_image(filename):
    return ("." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_PRODUCT_EXTENSIONS
    )

def get_db_connection():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="admin_app"
    )
    return connection

def send_otp(email, otp):
    sender_email = "322103384039@gvpce.ac.in"
    sender_password = "mndjjbrifkhmmden"
    message = EmailMessage()
    message["Subject"] = "Admin Registration OTP"
    message["From"] = sender_email
    message["To"] = email
    message.set_content(
        f"""
Hello,
Your OTP for admin registration is:
{otp}
This OTP is valid for 5 minutes.

Regards,
Admin Application
"""
    )

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(sender_email,sender_password)
        smtp.send_message(message)

@app.route("/admin/register", methods=["GET", "POST"])
def admin_register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM admins WHERE email = %s",
            (email,)
        )

        existing_admin = cursor.fetchone()
        if existing_admin:
            cursor.close()
            connection.close()
            return "Admin with this email already exists"

        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        )

        otp = str(random.randint(100000, 999999))
        otp_expiry = datetime.now() + timedelta(minutes=5)
        cursor.execute("""INSERT INTO admins
            (name,email,password,otp,otp_expiry,is_verified)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                name,
                email,
                hashed_password.decode("utf-8"),
                otp,
                otp_expiry,
                False
            )
        )
        connection.commit()
        cursor.close()
        connection.close()

        try:
            send_otp(email, otp)
        except Exception as e:
            print("OTP Email Error:", e)
            return f"Unable to send OTP: {e}"

        session["verification_email"] = email
        return redirect(url_for("verify_otp"))
    return render_template("admin_register.html")

@app.route("/admin/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if "verification_email" not in session:
        return redirect(url_for("admin_register"))

    email = session["verification_email"]
    if request.method == "POST":
        entered_otp = request.form["otp"]
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""SELECT * FROM admins
            WHERE email = %s""",(email,)
        )
        admin = cursor.fetchone()

        if not admin:
            cursor.close()
            connection.close()
            return "Admin not found"

        if admin["otp"] != entered_otp:
            cursor.close()
            connection.close()
            return "Invalid OTP"

        if datetime.now() > admin["otp_expiry"]:
            cursor.close()
            connection.close()
            return "OTP expired"
        cursor.execute("""UPDATE admins
            SET
                is_verified = TRUE,
                otp = NULL,
                otp_expiry = NULL
            WHERE email = %s
            """,(email,)
        )
        connection.commit()
        cursor.close()
        connection.close()
        session.pop("verification_email", None)
        return redirect(url_for("admin_login"))
    return render_template("verify_otp.html")

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""SELECT * FROM admins
            WHERE email = %s
            """,(email,)
        )
        admin = cursor.fetchone()
        cursor.close()
        connection.close()

        if not admin:
            return "Invalid email or password"
        if not admin["is_verified"]:
            return "Please verify your email first"

        password_correct = bcrypt.checkpw(
            password.encode("utf-8"),
            admin["password"].encode("utf-8")
        )
        if not password_correct:
            return "Invalid email or password"

        session["admin_id"] = admin["admin_id"]
        session["admin_name"] = admin["name"]
        session["admin_email"] = admin["email"]
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_login.html")

@app.route("/admin/profile")
def admin_profile():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""SELECT admin_id, name, email, profile_image
        FROM admins WHERE admin_id = %s""",
        (session["admin_id"],)
    )

    admin = cursor.fetchone()
    cursor.close()
    connection.close()

    if not admin:
        session.clear()
        return redirect(url_for("admin_login"))
    return render_template("admin_profile.html",admin=admin)

@app.route("/admin/profile/update", methods=["POST"])
def update_profile():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    name = request.form["name"]
    email = request.form["email"]

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""SELECT admin_id
        FROM admins WHERE email = %s AND admin_id != %s""",
        (email,session["admin_id"])
    )


    existing_admin = cursor.fetchone()
    if existing_admin:
        cursor.close()
        connection.close()
        return "Email already belongs to another admin"

    cursor.execute("""UPDATE admins
        SET name = %s, email = %s WHERE admin_id = %s
        """,(name,email,session["admin_id"])
    )
    connection.commit()
    cursor.close()
    connection.close()

    session["admin_name"] = name
    session["admin_email"] = email
    return redirect(url_for("admin_profile"))

@app.route("/admin/profile/image", methods=["POST"])
def upload_profile_image():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    if "profile_image" not in request.files:
        return "No image selected"

    file = request.files["profile_image"]

    if file.filename == "":
        return "No image selected"

    if not allowed_file(file.filename):
        return "Invalid image format"

    filename = secure_filename(file.filename)
    extension = filename.rsplit(".", 1)[1].lower()
    filename = f"admin_{session['admin_id']}.{extension}"

    upload_path = os.path.join(app.config["UPLOAD_FOLDER"],filename)
    file.save(upload_path)

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("""UPDATE admins
        SET profile_image = %s WHERE admin_id = %s
        """,(filename,session["admin_id"])
    )

    connection.commit()
    cursor.close()
    connection.close()
    return redirect(url_for("admin_profile"))


@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Admin details
    cursor.execute("""
        SELECT admin_id, name, email, profile_image
        FROM admins
        WHERE admin_id = %s
    """, (session["admin_id"],))

    admin = cursor.fetchone()

    if not admin:
        cursor.close()
        connection.close()
        session.clear()
        return redirect(url_for("admin_login"))

    # Total users
    cursor.execute("""
        SELECT COUNT(*) AS total_users
        FROM users
    """)
    total_users = cursor.fetchone()["total_users"]

    # Total orders
    cursor.execute("""
        SELECT COUNT(*) AS total_orders
        FROM orders
    """)
    total_orders = cursor.fetchone()["total_orders"]

    # Paid orders
    cursor.execute("""
        SELECT COUNT(*) AS paid_orders
        FROM orders
        WHERE payment_status = 'Paid'
    """)
    paid_orders = cursor.fetchone()["paid_orders"]

    # Pending / Processing orders
    cursor.execute("""
        SELECT COUNT(*) AS pending_orders
        FROM orders
        WHERE status IN ('Placed', 'Processing')
    """)
    pending_orders = cursor.fetchone()["pending_orders"]

    # Total revenue
    cursor.execute("""
        SELECT COALESCE(SUM(total_amount), 0) AS total_revenue
        FROM orders
        WHERE payment_status = 'Paid'
    """)
    total_revenue = cursor.fetchone()["total_revenue"]

    cursor.close()
    connection.close()

    return render_template(
        "admin_dashboard.html",
        admin=admin,
        total_users=total_users,
        total_orders=total_orders,
        paid_orders=paid_orders,
        pending_orders=pending_orders,
        total_revenue=total_revenue
    )


@app.route("/admin/products/add", methods=["GET", "POST"])
def add_product():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        price = request.form["price"]
        category = request.form["category"]
        stock = request.form["stock"]
        image = request.files.get("image")
        image_filename = None
        if image and image.filename != "":
            if not allowed_product_image(image.filename):
                return "Invalid image format"

            original_filename = secure_filename(image.filename)
            extension = original_filename.rsplit(
                ".",1)[1].lower()

            image_filename = (
                f"product_{datetime.now().strftime('%Y%m%d%H%M%S%f')}."
                f"{extension}"
            )

            image_path = os.path.join(app.config["PRODUCT_UPLOAD_FOLDER"],image_filename)
            image.save(image_path)

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO products
            (name, description, price, category, stock, image)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                name,
                description,
                price,
                category,
                stock,
                image_filename
            )
        )
        connection.commit()
        cursor.close()
        connection.close()
        return redirect(url_for("products"))
    return render_template("add_product.html")


@app.route("/admin/products/replace-image/<int:product_id>",
           methods=["POST"])
def replace_product_image(product_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    image = request.files.get("image")
    if not image or image.filename == "":
        return "Please select an image"

    allowed_extensions = {"png", "jpg", "jpeg", "gif", "webp"}
    filename = secure_filename(image.filename)

    if "." not in filename:
        return "Invalid image format"

    extension = filename.rsplit(".", 1)[1].lower()
    if extension not in allowed_extensions:
        return "Invalid image format"

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        "SELECT image FROM products WHERE product_id = %s",
        (product_id,)
    )
    product = cursor.fetchone()

    if not product:
        cursor.close()
        connection.close()
        return "Product not found"

    old_image = product["image"]

    upload_folder = os.path.join(app.root_path,"static","products")
    os.makedirs(upload_folder, exist_ok=True)

    new_filename = (
        f"product_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.{extension}"
    )

    image_path = os.path.join(upload_folder,new_filename)
    image.save(image_path)

    cursor.execute(
        """
        UPDATE products SET image = %s WHERE product_id = %s
        """,(new_filename, product_id)
    )
    connection.commit()
    cursor.close()
    connection.close()

    if old_image:
        old_image_path = os.path.join(upload_folder,old_image)

        if os.path.exists(old_image_path):
            os.remove(old_image_path)

    return redirect(url_for("product_view",
            product_id=product_id)
    )

@app.route("/admin/products/<int:product_id>")
def product_view(product_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """SELECT admin_id, name, email, profile_image
        FROM admins WHERE admin_id = %s""",
        (session["admin_id"],)
    )

    admin = cursor.fetchone()
    cursor.execute(
        """SELECT * FROM products WHERE product_id = %s""",
        (product_id,)
    )
    product = cursor.fetchone()
    cursor.close()
    connection.close()

    if not product:
        return "Product not found", 404

    return render_template("product_view.html",
        product=product,admin=admin,
        name=session["admin_name"],email=session["admin_email"]
    )


@app.route("/admin/products/update/<int:product_id>",
           methods=["GET", "POST"])
def update_product(product_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """SELECT * FROM products WHERE product_id = %s""",
        (product_id,)
    )

    product = cursor.fetchone()
    if not product:
        cursor.close()
        connection.close()
        return "Product not found"
    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        price = request.form["price"]
        category = request.form["category"]
        stock = request.form["stock"]
        cursor.execute("""UPDATE products
            SET name = %s,
                description = %s,
                price = %s,
                category = %s,
                stock = %s
            WHERE product_id = %s
            """,(
                name,
                description,
                price,
                category,
                stock,
                product_id
            )
        )
        connection.commit()
        cursor.close()
        connection.close()
        return redirect(url_for("product_view",
            product_id=product_id
        ))

    cursor.close()
    connection.close()
    return render_template(
        "update_product.html",
        product=product
    )

@app.route("/admin/products/delete/<int:product_id>",
           methods=["POST"])
def delete_product(product_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""SELECT image FROM products
        WHERE product_id = %s""",(product_id,)
    )

    product = cursor.fetchone()
    if not product:
        cursor.close()
        connection.close()
        return "Product not found"
    image_name = product["image"]
    cursor.execute("""DELETE FROM products
        WHERE product_id = %s
        """,(product_id,)
    )
    connection.commit()
    cursor.close()
    connection.close()

    if image_name:
        image_path = os.path.join(
            app.config["PRODUCT_UPLOAD_FOLDER"],
            image_name
        )
        if os.path.exists(image_path):
            os.remove(image_path)
    return redirect(url_for("products"))

@app.route("/admin/products")
def products():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM admins WHERE admin_id = %s",
        (session["admin_id"],)
    )
    admin = cursor.fetchone()

    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    query = """SELECT * FROM products WHERE 1 = 1"""
    values = []

    if search:
        query += """AND (name LIKE %s OR description LIKE %s)"""
        search_value = f"%{search}%"
        values.append(search_value)
        values.append(search_value)

    if category:
        query += " AND category = %s"
        values.append(category)

    query += " ORDER BY product_id DESC"

    cursor.execute(query, tuple(values))
    products = cursor.fetchall()

    cursor.execute("""SELECT DISTINCT category
        FROM products WHERE category IS NOT NULL
        AND category != '' ORDER BY category"""
    )

    categories = cursor.fetchall()
    cursor.close()
    connection.close()

    return render_template(
        "products.html",
        products=products,
        categories=categories,
        search=search,
        selected_category=category,
        admin=admin,
        name=session["admin_name"],
        email=session["admin_email"]
    )

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/admin/users")
def admin_users():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    search = request.args.get("search", "").strip()

    query = """
        SELECT user_id, name, email, is_verified, profile_image, created_at
        FROM users WHERE 1=1
    """
    values = []

    if search:
        query += " AND (name LIKE %s OR email LIKE %s)"
        v = f"%{search}%"
        values.extend([v, v])

    query += " ORDER BY user_id DESC"
    cursor.execute(query, tuple(values))
    users = cursor.fetchall()

    for user in users:
        cursor.execute(
            "SELECT COUNT(*) AS order_count FROM orders WHERE user_id=%s",
            (user["user_id"],)
        )
        user["order_count"] = cursor.fetchone()["order_count"]

    cursor.close()
    connection.close()

    return render_template(
        "admin_users.html",
        users=users,
        search=search
    )


@app.route("/admin/users/<int:user_id>")
def admin_user_details(user_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT user_id, name, email, is_verified, profile_image, created_at
        FROM users WHERE user_id=%s
    """, (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        connection.close()
        return "User not found", 404

    cursor.execute("""
        SELECT order_id, total_amount, status, payment_status,
               razorpay_order_id, razorpay_payment_id, created_at
        FROM orders
        WHERE user_id=%s
        ORDER BY order_id DESC
    """, (user_id,))
    orders = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin_user_details.html",
        user=user,
        orders=orders
    )


@app.route("/admin/orders")
def admin_orders():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    payment_status = request.args.get("payment_status", "").strip()

    query = """
        SELECT o.order_id, o.user_id, o.total_amount, o.status,
               o.payment_status, o.razorpay_order_id,
               o.razorpay_payment_id, o.created_at,
               u.name AS user_name, u.email AS user_email
        FROM orders o
        JOIN users u ON o.user_id=u.user_id
        WHERE 1=1
    """
    values = []

    if search:
        query += """
            AND (CAST(o.order_id AS CHAR) LIKE %s
            OR u.name LIKE %s
            OR u.email LIKE %s
            OR o.razorpay_payment_id LIKE %s)
        """
        v = f"%{search}%"
        values.extend([v, v, v, v])

    if status:
        query += " AND o.status=%s"
        values.append(status)

    if payment_status:
        query += " AND o.payment_status=%s"
        values.append(payment_status)

    query += " ORDER BY o.order_id DESC"
    cursor.execute(query, tuple(values))
    orders = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin_orders.html",
        orders=orders,
        search=search,
        selected_status=status,
        selected_payment_status=payment_status
    )


@app.route("/admin/orders/<int:order_id>")
def admin_order_details(order_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT o.order_id, o.user_id, o.total_amount, o.status,
               o.payment_status, o.razorpay_order_id,
               o.razorpay_payment_id, o.razorpay_signature,
               o.created_at, u.name AS user_name,
               u.email AS user_email
        FROM orders o
        JOIN users u ON o.user_id=u.user_id
        WHERE o.order_id=%s
    """, (order_id,))
    order = cursor.fetchone()

    if not order:
        cursor.close()
        connection.close()
        return "Order not found", 404

    cursor.execute("""
        SELECT oi.order_item_id, oi.product_id, oi.quantity, oi.price,
               p.name, p.image,
               (oi.quantity * oi.price) AS subtotal
        FROM order_items oi
        JOIN products p ON oi.product_id=p.product_id
        WHERE oi.order_id=%s
        ORDER BY oi.order_item_id
    """, (order_id,))
    items = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin_order_details.html",
        order=order,
        items=items
    )


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
def admin_update_order_status(order_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    new_status = request.form.get("status", "").strip()
    allowed = {"Placed", "Processing", "Shipped", "Delivered", "Cancelled"}

    if new_status not in allowed:
        return "Invalid order status", 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT order_id, status, payment_status
        FROM orders WHERE order_id=%s
    """, (order_id,))
    order = cursor.fetchone()

    if not order:
        cursor.close()
        connection.close()
        return "Order not found", 404

    if (order["payment_status"] != "Paid" and
            new_status in {"Processing", "Shipped", "Delivered"}):
        cursor.close()
        connection.close()
        return "Only paid orders can be processed, shipped, or delivered", 400

    cursor.execute("""
        UPDATE orders SET status=%s WHERE order_id=%s
    """, (new_status, order_id))

    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for("admin_order_details", order_id=order_id))


def send_user_otp(email, otp):
    sender_email = "322103384039@gvpce.ac.in"
    sender_password = "mndjjbrifkhmmden"

    message = EmailMessage()
    message["Subject"] = "BuyNest User Registration OTP"
    message["From"] = sender_email
    message["To"] = email
    message.set_content(
        f"""
Hello,
Your OTP for BuyNest user registration is:
{otp}
This OTP is valid for 5 minutes.

Regards,
BuyNest Team
"""
    )

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(sender_email, sender_password)
        smtp.send_message(message)



@app.route("/user/register", methods=["GET", "POST"])
def user_register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if not name or not email or not password:
            return "All fields are required"

        if password != confirm_password:
            return "Passwords do not match"

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT user_id, is_verified FROM users WHERE email = %s",
            (email,)
        )
        existing_user = cursor.fetchone()

        if existing_user:
            cursor.close()
            connection.close()

            if not existing_user["is_verified"]:
                session["verification_email"] = email
                return redirect(url_for("user_verify_otp"))

            return "User with this email already exists"

        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        otp = str(random.randint(100000, 999999))
        otp_expiry = datetime.now() + timedelta(minutes=5)

        cursor.execute(
            """
            INSERT INTO users
            (name, email, password, otp, otp_expiry, is_verified)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (name, email, hashed_password, otp, otp_expiry, False)
        )

        connection.commit()
        cursor.close()
        connection.close()

        try:
            send_user_otp(email, otp)
        except Exception as e:
            print("User OTP Email Error:", e)
            return f"Unable to send OTP: {e}"

        session["verification_email"] = email
        return redirect(url_for("user_verify_otp"))

    return render_template("user_register.html")



@app.route("/user/verify-otp", methods=["GET", "POST"])
def user_verify_otp():
    if "verification_email" not in session:
        return redirect(url_for("user_register"))

    email = session["verification_email"]

    if request.method == "POST":
        entered_otp = request.form["otp"].strip()

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE email = %s",
            (email,)
        )
        user = cursor.fetchone()

        if not user:
            cursor.close()
            connection.close()
            return "User not found"

        if user["is_verified"]:
            cursor.close()
            connection.close()
            session.pop("verification_email", None)
            return redirect(url_for("user_login"))

        if not user["otp"] or user["otp"] != entered_otp:
            cursor.close()
            connection.close()
            return "Invalid OTP"

        if not user["otp_expiry"] or datetime.now() > user["otp_expiry"]:
            cursor.close()
            connection.close()
            return "OTP expired. Please register again."

        cursor.execute(
            """
            UPDATE users
            SET is_verified = TRUE,
                otp = NULL,
                otp_expiry = NULL
            WHERE email = %s
            """,
            (email,)
        )

        connection.commit()
        cursor.close()
        connection.close()

        session.pop("verification_email", None)
        return redirect(url_for("user_login"))

    return render_template("user_verify_otp.html", email=email)



@app.route("/user/login", methods=["GET", "POST"])
def user_login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE email = %s",
            (email,)
        )
        user = cursor.fetchone()

        cursor.close()
        connection.close()

        if not user:
            return "Invalid email or password"

        if not user["is_verified"]:
            session["verification_email"] = email
            return redirect(url_for("user_verify_otp"))

        try:
            password_correct = bcrypt.checkpw(
                password.encode("utf-8"),
                user["password"].encode("utf-8")
            )
        except (ValueError, AttributeError):
            password_correct = False

        if not password_correct:
            return "Invalid email or password"

        session["user_id"] = user["user_id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]

        return redirect(url_for("user_dashboard"))

    return render_template("user_login.html")



@app.route("/user/dashboard")
def user_dashboard():
    if "user_id" not in session:
        return redirect(url_for("user_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()

    query = """
        SELECT *
        FROM products
        WHERE 1 = 1
    """
    values = []

    if search:
        query += """
            AND (name LIKE %s OR description LIKE %s)
        """
        search_value = f"%{search}%"
        values.extend([search_value, search_value])

    if category:
        query += " AND category = %s"
        values.append(category)

    query += " ORDER BY product_id DESC"

    cursor.execute(query, tuple(values))
    products = cursor.fetchall()

    cursor.execute(
        """
        SELECT DISTINCT category
        FROM products
        WHERE category IS NOT NULL
          AND category != ''
        ORDER BY category
        """
    )
    categories = cursor.fetchall()

    cursor.execute(
        """
        SELECT COALESCE(SUM(quantity), 0) AS cart_count
        FROM cart
        WHERE user_id = %s
        """,
        (session["user_id"],)
    )
    cart_count = cursor.fetchone()["cart_count"]

    cursor.close()
    connection.close()

    return render_template(
        "user_dashboard.html",
        products=products,
        categories=categories,
        search=search,
        selected_category=category,
        cart_count=cart_count,
        user_name=session["user_name"],
        user_email=session["user_email"]
    )



@app.route("/user/products/<int:product_id>")
def user_product_view(product_id):
    if "user_id" not in session:
        return redirect(url_for("user_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM products WHERE product_id = %s",
        (product_id,)
    )
    product = cursor.fetchone()

    cursor.close()
    connection.close()

    if not product:
        return "Product not found", 404

    return render_template(
        "user_product_view.html",
        product=product
    )



@app.route("/user/profile")
def user_profile():
    if "user_id" not in session:
        return redirect(url_for("user_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT user_id, name, email, profile_image, created_at
        FROM users
        WHERE user_id = %s
        """,
        (session["user_id"],)
    )
    user = cursor.fetchone()

    cursor.close()
    connection.close()

    if not user:
        session.clear()
        return redirect(url_for("user_login"))

    return render_template("user_profile.html", user=user)



@app.route("/user/profile/update", methods=["POST"])
def update_user_profile():
    if "user_id" not in session:
        return redirect(url_for("user_login"))

    name = request.form["name"].strip()
    email = request.form["email"].strip().lower()

    if not name or not email:
        return "Name and email are required"

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT user_id
        FROM users
        WHERE email = %s AND user_id != %s
        """,
        (email, session["user_id"])
    )
    existing_user = cursor.fetchone()

    if existing_user:
        cursor.close()
        connection.close()
        return "Email already belongs to another user"

    cursor.execute(
        """
        UPDATE users
        SET name = %s, email = %s
        WHERE user_id = %s
        """,
        (name, email, session["user_id"])
    )

    connection.commit()
    cursor.close()
    connection.close()

    session["user_name"] = name
    session["user_email"] = email

    return redirect(url_for("user_profile"))



@app.route("/user/profile/image", methods=["POST"])
def upload_user_profile_image():
    if "user_id" not in session:
        return redirect(url_for("user_login"))

    if "profile_image" not in request.files:
        return "No image selected"

    file = request.files["profile_image"]

    if file.filename == "":
        return "No image selected"

    if not allowed_file(file.filename):
        return "Invalid image format"

    filename = secure_filename(file.filename)
    extension = filename.rsplit(".", 1)[1].lower()
    filename = f"user_{session['user_id']}.{extension}"

    upload_folder = app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)

    upload_path = os.path.join(upload_folder, filename)
    file.save(upload_path)

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE users
        SET profile_image = %s
        WHERE user_id = %s
        """,
        (filename, session["user_id"])
    )

    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for("user_profile"))



@app.route("/user/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    if "user_id" not in session:
        return redirect(url_for("user_login"))

    quantity = request.form.get("quantity", 1, type=int)

    if quantity < 1:
        quantity = 1

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        "SELECT product_id, stock FROM products WHERE product_id = %s",
        (product_id,)
    )
    product = cursor.fetchone()

    if not product:
        cursor.close()
        connection.close()
        return "Product not found", 404

    if product["stock"] <= 0:
        cursor.close()
        connection.close()
        return "Product is out of stock"

    cursor.execute(
        """
        SELECT cart_id, quantity
        FROM cart
        WHERE user_id = %s AND product_id = %s
        """,
        (session["user_id"], product_id)
    )
    existing_item = cursor.fetchone()

    if existing_item:
        new_quantity = existing_item["quantity"] + quantity

        if new_quantity > product["stock"]:
            new_quantity = product["stock"]

        cursor.execute(
            """
            UPDATE cart
            SET quantity = %s
            WHERE cart_id = %s
            """,
            (new_quantity, existing_item["cart_id"])
        )
    else:
        if quantity > product["stock"]:
            quantity = product["stock"]

        cursor.execute(
            """
            INSERT INTO cart (user_id, product_id, quantity)
            VALUES (%s, %s, %s)
            """,
            (session["user_id"], product_id, quantity)
        )

    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for("user_cart"))



@app.route("/user/cart")
def user_cart():
    if "user_id" not in session:
        return redirect(url_for("user_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            c.cart_id,
            c.product_id,
            c.quantity,
            p.name,
            p.description,
            p.price,
            p.stock,
            p.image,
            (c.quantity * p.price) AS subtotal
        FROM cart c
        JOIN products p
          ON c.product_id = p.product_id
        WHERE c.user_id = %s
        ORDER BY c.cart_id DESC
        """,
        (session["user_id"],)
    )

    cart_items = cursor.fetchall()

    total = sum(float(item["subtotal"]) for item in cart_items)

    cursor.close()
    connection.close()

    return render_template(
        "user_cart.html",
        cart_items=cart_items,
        total=total
    )



@app.route("/user/cart/update/<int:cart_id>", methods=["POST"])
def update_cart(cart_id):
    if "user_id" not in session:
        return redirect(url_for("user_login"))

    quantity = request.form.get("quantity", 1, type=int)

    if quantity < 1:
        return redirect(url_for("user_cart"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT c.cart_id, p.stock
        FROM cart c
        JOIN products p ON c.product_id = p.product_id
        WHERE c.cart_id = %s AND c.user_id = %s
        """,
        (cart_id, session["user_id"])
    )
    item = cursor.fetchone()

    if not item:
        cursor.close()
        connection.close()
        return "Cart item not found", 404

    if quantity > item["stock"]:
        quantity = item["stock"]

    cursor.execute(
        """
        UPDATE cart
        SET quantity = %s
        WHERE cart_id = %s AND user_id = %s
        """,
        (quantity, cart_id, session["user_id"])
    )

    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for("user_cart"))



@app.route("/user/cart/remove/<int:cart_id>", methods=["POST"])
def remove_from_cart(cart_id):
    if "user_id" not in session:
        return redirect(url_for("user_login"))

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM cart
        WHERE cart_id = %s AND user_id = %s
        """,
        (cart_id, session["user_id"])
    )

    connection.commit()
    cursor.close()
    connection.close()

    return redirect(url_for("user_cart"))



@app.route("/user/checkout")
def user_checkout():
    if "user_id" not in session:
        return redirect(url_for("user_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            c.cart_id,
            c.product_id,
            c.quantity,
            p.name,
            p.price,
            p.stock,
            p.image,
            (c.quantity * p.price) AS subtotal
        FROM cart c
        JOIN products p ON c.product_id = p.product_id
        WHERE c.user_id = %s
        ORDER BY c.cart_id DESC
        """,
        (session["user_id"],)
    )

    cart_items = cursor.fetchall()

    cursor.close()
    connection.close()

    if not cart_items:
        return redirect(url_for("user_cart"))

    # Validate stock before showing checkout.
    for item in cart_items:
        if item["quantity"] > item["stock"]:
            return (
                f"Insufficient stock for {item['name']}. "
                f"Available stock: {item['stock']}"
            )

    total = sum(float(item["subtotal"]) for item in cart_items)

    return render_template(
        "user_checkout.html",
        cart_items=cart_items,
        total=total
    )


@app.route("/user/create-payment-order", methods=["POST"])
def create_payment_order():
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Please login first."
        }), 401

    if razorpay_client is None:
        return jsonify({
            "success": False,
            "message": (
                "Razorpay credentials are not configured. "
                "Add your Razorpay TEST secret to RAZORPAY_KEY_SECRET "
                "in this file or set it in PyCharm Environment Variables."
            )
        }), 500

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Re-read the cart from the database.
        cursor.execute(
            """
            SELECT
                c.cart_id,
                c.product_id,
                c.quantity,
                p.name,
                p.price,
                p.stock,
                (c.quantity * p.price) AS subtotal
            FROM cart c
            JOIN products p ON c.product_id = p.product_id
            WHERE c.user_id = %s
            FOR UPDATE
            """,
            (session["user_id"],)
        )

        cart_items = cursor.fetchall()

        if not cart_items:
            return jsonify({
                "success": False,
                "message": "Your cart is empty."
            }), 400

        # Check current stock again immediately before creating payment.
        for item in cart_items:
            if item["quantity"] > item["stock"]:
                return jsonify({
                    "success": False,
                    "message": (
                        f"Insufficient stock for {item['name']}. "
                        f"Available stock: {item['stock']}"
                    )
                }), 400

        total = sum(
            float(item["subtotal"])
            for item in cart_items
        )

        amount_paise = int(round(total * 100))

        if amount_paise <= 0:
            return jsonify({
                "success": False,
                "message": "Invalid order amount."
            }), 400

        # Create Razorpay order.
        razorpay_order = razorpay_client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": (
                f"BUYNEST_{session['user_id']}_"
                f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            ),
            "notes": {
                "user_id": str(session["user_id"])
            }
        })

        # Create a local pending order.
        cursor.execute(
            """
            INSERT INTO orders
            (
                user_id,
                total_amount,
                status,
                payment_status,
                razorpay_order_id
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                session["user_id"],
                total,
                "Payment Pending",
                "Pending",
                razorpay_order["id"]
            )
        )

        order_id = cursor.lastrowid

        # Save order items, but DO NOT reduce stock yet.
        for item in cart_items:
            cursor.execute(
                """
                INSERT INTO order_items
                (order_id, product_id, quantity, price)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    order_id,
                    item["product_id"],
                    item["quantity"],
                    item["price"]
                )
            )

        connection.commit()

        return jsonify({
            "success": True,
            "key_id": RAZORPAY_KEY_ID,
            "razorpay_order_id": razorpay_order["id"],
            "amount": amount_paise,
            "currency": "INR",
            "order_id": order_id
        })

    except Exception as e:
        connection.rollback()

        print("====================================")
        print("RAZORPAY ERROR:", repr(e))
        print("RAZORPAY KEY ID:", RAZORPAY_KEY_ID)
        print("RAZORPAY SECRET SET:", bool(RAZORPAY_KEY_SECRET))
        print("====================================")

        return jsonify({
            "success": False,
            "message": "Unable to create payment order."
        }), 500
    finally:
        cursor.close()
        connection.close()


@app.route("/user/verify-payment", methods=["POST"])
def verify_payment():
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Please login first."
        }), 401

    data = request.get_json(silent=True) or {}

    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_signature = data.get("razorpay_signature")

    if not all([
        razorpay_order_id,
        razorpay_payment_id,
        razorpay_signature
    ]):
        return jsonify({
            "success": False,
            "message": "Incomplete payment information."
        }), 400

    if razorpay_client is None:
        return jsonify({
            "success": False,
            "message": (
                "Razorpay credentials are not configured. "
                "Add your Razorpay TEST secret to RAZORPAY_KEY_SECRET "
                "in this file or set it in PyCharm Environment Variables."
            )
        }), 500

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Verify the Razorpay signature first.
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature
        })

        # Lock the local order so a duplicate verification cannot
        # reduce stock or clear the cart twice.
        cursor.execute(
            """
            SELECT
                order_id,
                user_id,
                total_amount,
                status,
                payment_status,
                razorpay_order_id
            FROM orders
            WHERE razorpay_order_id = %s
              AND user_id = %s
            FOR UPDATE
            """,
            (
                razorpay_order_id,
                session["user_id"]
            )
        )

        order = cursor.fetchone()

        if not order:
            connection.rollback()
            return jsonify({
                "success": False,
                "message": "Local order not found."
            }), 404

        # Idempotency: if this payment was already processed,
        # do not reduce stock a second time.
        if order["payment_status"] == "Paid":
            connection.commit()
            return jsonify({
                "success": True,
                "message": "Payment was already verified.",
                "order_id": order["order_id"]
            })

        # Get the items belonging to this order.
        cursor.execute(
            """
            SELECT
                oi.product_id,
                oi.quantity,
                oi.price,
                p.name,
                p.stock
            FROM order_items oi
            JOIN products p
              ON oi.product_id = p.product_id
            WHERE oi.order_id = %s
            FOR UPDATE
            """,
            (order["order_id"],)
        )

        order_items = cursor.fetchall()

        if not order_items:
            connection.rollback()
            return jsonify({
                "success": False,
                "message": "Order items were not found."
            }), 404

        # Re-check stock at the exact moment payment is confirmed.
        for item in order_items:
            if item["quantity"] > item["stock"]:
                connection.rollback()

                return jsonify({
                    "success": False,
                    "message": (
                        f"Insufficient stock for {item['name']} "
                        "after payment verification. "
                        "Please contact the BuyNest administrator "
                        "for refund processing."
                    )
                }), 409

        # Mark payment as successful.
        cursor.execute(
            """
            UPDATE orders
            SET
                payment_status = 'Paid',
                status = 'Placed',
                razorpay_payment_id = %s,
                razorpay_signature = %s
            WHERE order_id = %s
              AND user_id = %s
            """,
            (
                razorpay_payment_id,
                razorpay_signature,
                order["order_id"],
                session["user_id"]
            )
        )

        # Reduce stock only after successful payment verification.
        for item in order_items:
            cursor.execute(
                """
                UPDATE products
                SET stock = stock - %s
                WHERE product_id = %s
                  AND stock >= %s
                """,
                (
                    item["quantity"],
                    item["product_id"],
                    item["quantity"]
                )
            )

            if cursor.rowcount != 1:
                connection.rollback()

                return jsonify({
                    "success": False,
                    "message": (
                        f"Stock changed for {item['name']}. "
                        "Please contact the BuyNest administrator "
                        "for refund processing."
                    )
                }), 409

        # Clear the cart only after successful payment.
        cursor.execute(
            """
            DELETE FROM cart
            WHERE user_id = %s
            """,
            (session["user_id"],)
        )

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Payment verified successfully.",
            "order_id": order["order_id"]
        })

    except razorpay.errors.SignatureVerificationError:
        connection.rollback()

        return jsonify({
            "success": False,
            "message": "Payment signature verification failed."
        }), 400

    except Exception as e:
        connection.rollback()
        print("Payment Verification Error:", e)

        return jsonify({
            "success": False,
            "message": "Unable to verify payment."
        }), 500

    finally:
        cursor.close()
        connection.close()


@app.route("/user/orders")
def user_orders():
    if "user_id" not in session:
        return redirect(url_for("user_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            order_id,
            total_amount,
            status,
            payment_status,
            razorpay_order_id,
            razorpay_payment_id,
            created_at
        FROM orders
        WHERE user_id = %s
        ORDER BY order_id DESC
        """,
        (session["user_id"],)
    )

    orders = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "user_orders.html",
        orders=orders
    )


@app.route("/user/orders/<int:order_id>")
def user_order_details(order_id):
    if "user_id" not in session:
        return redirect(url_for("user_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            o.order_id,
            o.total_amount,
            o.status,
            o.payment_status,
            o.razorpay_order_id,
            o.razorpay_payment_id,
            o.created_at,
            oi.product_id,
            oi.quantity,
            oi.price,
            p.name,
            p.image
        FROM orders o
        JOIN order_items oi
          ON o.order_id = oi.order_id
        JOIN products p
          ON oi.product_id = p.product_id
        WHERE o.order_id = %s
          AND o.user_id = %s
        ORDER BY oi.order_item_id
        """,
        (order_id, session["user_id"])
    )

    items = cursor.fetchall()

    cursor.close()
    connection.close()

    if not items:
        return "Order not found", 404

    total = items[0]["total_amount"]
    status = items[0]["status"]
    payment_status = items[0]["payment_status"]
    razorpay_order_id = items[0]["razorpay_order_id"]
    razorpay_payment_id = items[0]["razorpay_payment_id"]
    created_at = items[0]["created_at"]

    return render_template(
        "user_order_details.html",
        order_id=order_id,
        items=items,
        total=total,
        status=status,
        payment_status=payment_status,
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        created_at=created_at
    )


@app.route("/user/logout")
def user_logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    session.pop("user_email", None)
    session.pop("verification_email", None)

    return redirect(url_for("user_login"))


if __name__ == "__main__":
    app.run(debug=True,port=9000)