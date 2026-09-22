from flask import Flask,render_template,request,redirect,url_for,flash,session
import mysql.connector
import bcrypt
import random
from datetime import datetime,timedelta
import smtplib
from email.message import EmailMessage
import os 
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
app=Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["PRODUCT_UPLOAD_FOLDER"] = os.path.join(
    app.root_path,"static","products"
)
os.makedirs(app.config["PRODUCT_UPLOAD_FOLDER"],exist_ok = True)
ALLOWED_EXTENSIONS = {"png","jpg","jpeg","gif","webp"}
def allowed_file(filename):
    return (
        "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXTENSIONS)
ALLOWED_PRODUCT_EXTENSIONS = {"jpg","jpeg","png","gif","webp"}
def allowed_product_image(filename):
    return (
        "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_PRODUCT_EXTENSIONS)
def get_db_connection():
    
    connection = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)
    return connection

def send_otp(email, otp):
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    
    message = EmailMessage()
    message["Subject"] = "Admin Registration OTP"
    message["From"] = sender_email
    message["To"] = email
    message.set_content(f"Your OTP for admin registration is: {otp}")
    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(sender_email, sender_password)
        smtp.send_message(message)

@app.route("/admin/register",methods=['GET','POST'])
def admin_register():
    if request.method=='POST':
        name=request.form['name']
        email=request.form['email']
        password=request.form['password']
        connection=get_db_connection()
        cursor=connection.cursor(dictionary=True)
        cursor.execute(
            "select * from admins where email=%s",
            (email,)
        )
        existing_admin=cursor.fetchone()
        if existing_admin:
            cursor.close()
            connection.close()
            return 'Admin with this email already exists'
        hashed_password=bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        )
        otp=str(random.randint(100000,999999))
        otp_expiry=datetime.now()+timedelta(minutes=5)
        cursor.execute(
            """insert into admins (name,email,password,otp,otp_expiry,is_verified) values (%s,%s,%s,%s,%s,%s)""",
            (name,email,hashed_password.decode('utf-8'),otp,otp_expiry,False)
        )
        connection.commit()
        cursor.close()
        connection.close()
        try:
            send_otp(email,otp)
        except Exception as e:
            print("OTP Email Error:",e)
            return f"Unable to send OTP:{e}"
        session['verification_email']=email
        return redirect(url_for("verify_otp"))
    return render_template('admin_register.html')

@app.route("/admin/verify-otp",methods=["GET","POST"])
def verify_otp():
    if "verification_email" not in session:
        return redirect(url_for("admin_register"))
    email=session['verification_email']
    if request.method=="POST":
        entered_otp=request.form['otp']
        connection=get_db_connection()
        cursor=connection.cursor(dictionary=True)
        cursor.execute(
            """select *from admins where email=%s""",(email,)
        )
        admin=cursor.fetchone()
        if not admin:
            cursor.close()
            connection.close()
            return "Admin not found"
        if admin['otp']!=entered_otp:
            cursor.close()
            connection.close()
            return 'Invalid OTP'
        if datetime.now()>admin['otp_expiry']:
            cursor.close()
            connection.close()
            return "OTP Expired"
        cursor.execute(
            """update admins set is_verified=TRUE,otp=NULL,otp_expiry=NULL where email=%s""",(email,)
        )
        connection.commit()
        cursor.close()
        connection.close()
        session.pop("verification_email",None)
        return redirect(url_for("admin_login"))
    return render_template("verify_otp.html")

@app.route("/admin/login",methods=["GET","POST"])
def admin_login():
    if request.method=="POST":
        email=request.form["email"]
        password=request.form["password"]
        connection=get_db_connection()
        cursor=connection.cursor(dictionary=True)
        cursor.execute(
            """select * from admins where email=%s""",(email,)
        )
        admin=cursor.fetchone()
        cursor.close()
        connection.close()
        if not admin:
            return "Invalid email or password"
        if not admin["is_verified"]:
            return "Please verify your email"
        password_correct=bcrypt.checkpw(
            password.encode("utf-8"),
            admin["password"].encode("utf-8")
        )
        if not password_correct:
            return "Invalid email or password"
        session["admin_id"]=admin["admin_id"]
        session["admin_name"]=admin["name"]
        session["admin_email"]=admin["email"]
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_login.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """select admin_id,name,email,profile_image from admins where admin_id = %s""",(session["admin_id"],)
    )
    admin = cursor.fetchone()
    cursor.close()
    connection.close()
    if not admin:
        session.clear()
        return redirect(url_for("admin_login"))
    return render_template(
        "admin_dashboard.html",admin=admin
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
            extension = original_filename.rsplit(".", 1)[1].lower()
            image_filename = f"product_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.{extension}"
            
            image_path = os.path.join(app.config["PRODUCT_UPLOAD_FOLDER"], image_filename)
            image.save(image_path)

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """INSERT INTO products (name, description, price, category, stock, image) 
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (name, description, price, category, stock, image_filename)
        )
        connection.commit()
        cursor.close()
        connection.close()

        flash("Product added successfully!", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("add_product.html")
@app.route("/admin/products")
def products():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT * FROM admins where admin_id = %s""",(session["admin_id"],)
    )
    admin = cursor.fetchone()
    search = request.args.get("search","").strip()
    category = request.args.get("category","").strip()
    query = """select * from products where 1=1"""
    values = []
    if search:
        query += """AND(name LIKE %s OR description LIKE %s)"""
        search_value = f"%{search}%"
        values.append(search_value)
        values.append(search_value)
        if category:
            query += " AND category = %s"
        values.append(category)
    query += "order by product_id desc"
    cursor.execute(query,tuple(values))
    products = cursor.fetchall()
    cursor.execute("""select distinct category from products where category IS NOT NULL AND category !=''ORDER BY category""")
    categories = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template(
        "products.html",
        products = products,
        categories = categories,
        search = search,
        selected_category = category,
        admin = admin,
        name = session["admin_name"],
        email= session["admin_email"]
    )

@app.route("/admin/products/update/<int:product_id>", methods=["GET", "POST"])
def update_product(product_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT * FROM products
        WHERE product_id = %s
        """,
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

        cursor.execute(
            """
            UPDATE products
            SET name = %s,
                description = %s,
                price = %s,
                category = %s,
                stock = %s
            WHERE product_id = %s
            """,
            (name, description, price, category, stock, product_id)
        )
        connection.commit()
        cursor.close()
        connection.close()
        return redirect(url_for("product_view", product_id=product_id))

    cursor.close()
    connection.close()
    return render_template("update_product.html", product=product)
@app.route("/admin/products/delete/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

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

    image_name = product["image"]
    cursor.execute(
        "DELETE FROM products WHERE product_id = %s",
        (product_id,)
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


@app.route("/admin/products/<int:product_id>")
def product_view(product_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))
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
        return "Product not found"
    return render_template(
        "product_view.html",
        product=product
    )
@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))
if __name__ == '__main__':
    app.run(debug=True)