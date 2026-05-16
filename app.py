
"""
Bookstore Web App
Customer Ordering + Admin Management
Flask + SQLAlchemy ORM + MySQL

Important:
- All saved bookstore records are stored directly in MySQL.
- No XML, JSON, CSV, TXT, or hardcoded data file is used for records.
- The app automatically creates the database and tables on startup.

Before running:
    python -m pip install -r requirements.txt

Run:
    python app.py

Open:
    http://127.0.0.1:5000
"""

import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from flask import Flask, render_template, request, redirect, url_for, flash, session
from sqlalchemy import create_engine, Column, Integer, String, Numeric, ForeignKey, DateTime, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session, relationship
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

# ==========================================================
# MYSQL CONFIGURATION
# ==========================================================
# On Railway, DATABASE_URL is set automatically by the MySQL service.
# Format: mysql+pymysql://user:password@host:port/database
# Falls back to localhost credentials for local development.

_DATABASE_URL = os.environ.get("DATABASE_URL", "")

if _DATABASE_URL:
    _parsed = urlparse(_DATABASE_URL)
    MYSQL_HOST = _parsed.hostname
    MYSQL_PORT = _parsed.port or 3306
    MYSQL_USER = _parsed.username
    MYSQL_PASSWORD = _parsed.password
    DATABASE_NAME = _parsed.path.lstrip("/")
else:
    MYSQL_HOST = "localhost"
    MYSQL_PORT = 3306
    MYSQL_USER = "root"
    MYSQL_PASSWORD = ""
    DATABASE_NAME = "bookstore_db"

# ==========================================================
# FLASK SETUP
# ==========================================================

app = Flask(__name__)
app.secret_key = "bookstore-secret-key-change-this"

Base = declarative_base()
DBSession = None


# ==========================================================
# ORM MODELS
# ==========================================================

class Author(Base):
    __tablename__ = "authors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)

    books = relationship("Book", back_populates="author")


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(150), nullable=False)
    genre = Column(String(80))
    price = Column(Numeric(10, 2), nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    description = Column(String(500))

    author_id = Column(Integer, ForeignKey("authors.id"), nullable=False)
    author = relationship("Author", back_populates="books")

    order_items = relationship("OrderItem", back_populates="book")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), nullable=False)
    phone = Column(String(30))
    address = Column(String(255))

    orders = relationship("Order", back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_date = Column(DateTime, default=datetime.now, nullable=False)
    status = Column(String(30), nullable=False, default="Pending")

    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    customer = relationship("Customer", back_populates="orders")

    order_items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)

    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)

    order = relationship("Order", back_populates="order_items")
    book = relationship("Book", back_populates="order_items")


# ==========================================================
# DATABASE SETUP
# ==========================================================

def make_url(database=None):
    return URL.create(
        drivername="mysql+pymysql",
        username=MYSQL_USER,
        password=MYSQL_PASSWORD,
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        database=database,
    )


def run_migrations(db_engine):
    """Add missing columns to existing tables."""
    with db_engine.connect() as conn:
        # Check if orders table has status column
        result = conn.execute(text("SHOW COLUMNS FROM orders LIKE 'status'"))
        status_column_exists = result.fetchone()
        
        if not status_column_exists:
            print("Migration: Adding 'status' column to orders table...")
            conn.execute(text("ALTER TABLE orders ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'Pending'"))
            conn.commit()
            print("Migration complete.")


def setup_database():
    """
    Automatically creates the database and tables.
    After this, all routes directly save data to MySQL.
    """
    global DBSession

    try:
        if _DATABASE_URL:
            # On Railway the database is already provisioned; connect directly.
            # Railway provides mysql:// but SQLAlchemy requires mysql+pymysql://
            # to use the pymysql driver instead of the unavailable MySQLdb driver.
            _engine_url = _DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)
            db_engine = create_engine(_engine_url)
        else:
            # Local development: create the database if it doesn't exist yet.
            server_engine = create_engine(make_url())
            with server_engine.connect() as conn:
                conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {DATABASE_NAME}"))
                conn.commit()
            db_engine = create_engine(make_url(DATABASE_NAME))

        Base.metadata.create_all(db_engine)
        
        # Run migrations for any missing columns
        run_migrations(db_engine)
        
        DBSession = scoped_session(sessionmaker(bind=db_engine))
        print(f"Connected to MySQL database: {DATABASE_NAME}")
        print("Database and tables are ready.")

    except SQLAlchemyError as error:
        print("ERROR: Cannot connect to MySQL.")
        print("Please check MYSQL_USER and MYSQL_PASSWORD in app.py.")
        print("Also make sure MySQL Server is running.")
        print(error)
        raise SystemExit


setup_database()


@app.teardown_appcontext
def remove_db_session(exception=None):
    if DBSession:
        DBSession.remove()


def db():
    return DBSession()


# ==========================================================
# HELPERS
# ==========================================================

def money(value):
    return Decimal(value).quantize(Decimal("0.01"))


@app.context_processor
def inject_cart_count():
    cart = session.get("cart", {})
    count = sum(cart.values()) if cart else 0
    return {"cart_count": count}


def get_cart_items(database):
    """Return cart item details from MySQL books table."""
    cart = session.get("cart", {})
    items = []
    total = Decimal("0.00")

    for book_id_text, qty in cart.items():
        book = database.query(Book).filter_by(id=int(book_id_text)).first()
        if not book:
            continue
        subtotal = book.price * qty
        total += subtotal
        items.append({
            "book": book,
            "quantity": qty,
            "subtotal": subtotal,
        })

    return items, total


# ==========================================================
# CUSTOMER SHOP ROUTES
# ==========================================================

@app.route("/")
def home():
    database = db()
    books = database.query(Book).filter(Book.stock > 0).order_by(Book.id.desc()).limit(6).all()
    return render_template("shop/home.html", books=books)


@app.route("/shop")
def shop():
    database = db()
    keyword = request.args.get("q", "").strip()
    genre = request.args.get("genre", "").strip()

    query = database.query(Book).filter(Book.stock > 0)
    if keyword:
        query = query.filter(Book.title.like(f"%{keyword}%"))
    if genre:
        query = query.filter(Book.genre == genre)

    books = query.order_by(Book.title).all()
    genres = [row[0] for row in database.query(Book.genre).filter(Book.genre != None).distinct().all()]

    return render_template("shop/shop.html", books=books, keyword=keyword, genre=genre, genres=genres)


@app.route("/book/<int:book_id>")
def book_detail(book_id):
    database = db()
    book = database.query(Book).filter_by(id=book_id).first()
    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for("shop"))
    return render_template("shop/book_detail.html", book=book)


@app.route("/cart")
def cart():
    database = db()
    items, total = get_cart_items(database)
    return render_template("shop/cart.html", items=items, total=total)


@app.route("/cart/add/<int:book_id>", methods=["POST"])
def add_to_cart(book_id):
    database = db()
    book = database.query(Book).filter_by(id=book_id).first()
    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for("shop"))

    try:
        quantity = int(request.form.get("quantity", 1))
    except ValueError:
        quantity = 1

    if quantity < 1:
        quantity = 1

    cart = session.get("cart", {})
    current_qty = cart.get(str(book_id), 0)

    if current_qty + quantity > book.stock:
        flash(f"Not enough stock. Available stock: {book.stock}", "danger")
        return redirect(url_for("book_detail", book_id=book_id))

    cart[str(book_id)] = current_qty + quantity
    session["cart"] = cart
    flash("Book added to cart.", "success")
    return redirect(url_for("cart"))


@app.route("/cart/update", methods=["POST"])
def update_cart():
    database = db()
    cart = session.get("cart", {})

    for key, value in request.form.items():
        if not key.startswith("qty_"):
            continue
        book_id = key.replace("qty_", "")
        book = database.query(Book).filter_by(id=int(book_id)).first()
        if not book:
            cart.pop(book_id, None)
            continue
        try:
            qty = int(value)
        except ValueError:
            qty = 1
        if qty <= 0:
            cart.pop(book_id, None)
        elif qty > book.stock:
            cart[book_id] = book.stock
            flash(f"Quantity for {book.title} was reduced to available stock.", "warning")
        else:
            cart[book_id] = qty

    session["cart"] = cart
    flash("Cart updated.", "success")
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:book_id>", methods=["POST"])
def remove_from_cart(book_id):
    cart = session.get("cart", {})
    cart.pop(str(book_id), None)
    session["cart"] = cart
    flash("Item removed from cart.", "success")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    database = db()
    items, total = get_cart_items(database)

    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("shop"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not name or not email or not address:
            flash("Name, email, and address are required.", "danger")
            return redirect(url_for("checkout"))

        # Recheck stock before saving order.
        for item in items:
            if item["quantity"] > item["book"].stock:
                flash(f"Not enough stock for {item['book'].title}.", "danger")
                return redirect(url_for("cart"))

        customer = Customer(name=name, email=email, phone=phone, address=address)
        order = Order(customer=customer, status="Pending")

        database.add(customer)
        database.add(order)

        for item in items:
            book = item["book"]
            qty = item["quantity"]
            order_item = OrderItem(order=order, book=book, quantity=qty, unit_price=book.price)
            book.stock -= qty
            database.add(order_item)

        try:
            database.commit()
            session["cart"] = {}
            flash("Order placed successfully. Your order was saved in MySQL.", "success")
            return redirect(url_for("order_success", order_id=order.id))
        except SQLAlchemyError as error:
            database.rollback()
            flash(f"Database error: {error}", "danger")
            return redirect(url_for("checkout"))

    return render_template("shop/checkout.html", items=items, total=total)


@app.route("/order-success/<int:order_id>")
def order_success(order_id):
    database = db()
    order = database.query(Order).filter_by(id=order_id).first()
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("shop"))
    return render_template("shop/order_success.html", order=order)


# ==========================================================
# ADMIN ROUTES
# ==========================================================

@app.route("/admin")
def admin_dashboard():
    database = db()
    return render_template(
        "admin/dashboard.html",
        author_count=database.query(Author).count(),
        book_count=database.query(Book).count(),
        customer_count=database.query(Customer).count(),
        order_count=database.query(Order).count(),
    )


# ---------------- AUTHORS ----------------

@app.route("/admin/authors")
def admin_authors():
    database = db()
    authors = database.query(Author).order_by(Author.id).all()
    return render_template("admin/authors.html", authors=authors)


@app.route("/admin/authors/add", methods=["GET", "POST"])
def admin_add_author():
    database = db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Author name is required.", "danger")
            return redirect(url_for("admin_add_author"))
        database.add(Author(name=name))
        try:
            database.commit()
            flash("Author saved to MySQL.", "success")
            return redirect(url_for("admin_authors"))
        except IntegrityError:
            database.rollback()
            flash("Author already exists.", "danger")
        except SQLAlchemyError as error:
            database.rollback()
            flash(f"Database error: {error}", "danger")
    return render_template("admin/author_form.html", author=None)


@app.route("/admin/authors/<int:author_id>/edit", methods=["GET", "POST"])
def admin_edit_author(author_id):
    database = db()
    author = database.query(Author).filter_by(id=author_id).first()
    if not author:
        flash("Author not found.", "danger")
        return redirect(url_for("admin_authors"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Author name is required.", "danger")
            return redirect(url_for("admin_edit_author", author_id=author_id))
        author.name = name
        try:
            database.commit()
            flash("Author updated.", "success")
            return redirect(url_for("admin_authors"))
        except IntegrityError:
            database.rollback()
            flash("Author name already exists.", "danger")
        except SQLAlchemyError as error:
            database.rollback()
            flash(f"Database error: {error}", "danger")
    return render_template("admin/author_form.html", author=author)


@app.route("/admin/authors/<int:author_id>/delete", methods=["POST"])
def admin_delete_author(author_id):
    database = db()
    author = database.query(Author).filter_by(id=author_id).first()
    if not author:
        flash("Author not found.", "danger")
        return redirect(url_for("admin_authors"))
    if author.books:
        flash("Cannot delete author with existing books.", "danger")
        return redirect(url_for("admin_authors"))
    try:
        database.delete(author)
        database.commit()
        flash("Author deleted.", "success")
    except SQLAlchemyError as error:
        database.rollback()
        flash(f"Database error: {error}", "danger")
    return redirect(url_for("admin_authors"))


# ---------------- BOOKS ----------------

@app.route("/admin/books")
def admin_books():
    database = db()
    books = database.query(Book).order_by(Book.id).all()
    return render_template("admin/books.html", books=books)


@app.route("/admin/books/add", methods=["GET", "POST"])
def admin_add_book():
    database = db()
    authors = database.query(Author).order_by(Author.name).all()
    if not authors:
        flash("Add an author first.", "warning")
        return redirect(url_for("admin_add_author"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        genre = request.form.get("genre", "").strip() or None
        description = request.form.get("description", "").strip() or None
        price_text = request.form.get("price", "").strip()
        stock_text = request.form.get("stock", "").strip()
        author_id_text = request.form.get("author_id", "").strip()

        try:
            price = Decimal(price_text)
            stock = int(stock_text)
            author_id = int(author_id_text)
            if price < 0 or stock < 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            flash("Invalid price, stock, or author.", "danger")
            return redirect(url_for("admin_add_book"))

        if not title:
            flash("Book title is required.", "danger")
            return redirect(url_for("admin_add_book"))

        database.add(Book(title=title, genre=genre, description=description, price=price, stock=stock, author_id=author_id))
        try:
            database.commit()
            flash("Book saved to MySQL.", "success")
            return redirect(url_for("admin_books"))
        except SQLAlchemyError as error:
            database.rollback()
            flash(f"Database error: {error}", "danger")
    return render_template("admin/book_form.html", book=None, authors=authors)


@app.route("/admin/books/<int:book_id>/edit", methods=["GET", "POST"])
def admin_edit_book(book_id):
    database = db()
    book = database.query(Book).filter_by(id=book_id).first()
    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for("admin_books"))
    authors = database.query(Author).order_by(Author.name).all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        genre = request.form.get("genre", "").strip() or None
        description = request.form.get("description", "").strip() or None
        price_text = request.form.get("price", "").strip()
        stock_text = request.form.get("stock", "").strip()
        author_id_text = request.form.get("author_id", "").strip()

        try:
            price = Decimal(price_text)
            stock = int(stock_text)
            author_id = int(author_id_text)
            if price < 0 or stock < 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            flash("Invalid price, stock, or author.", "danger")
            return redirect(url_for("admin_edit_book", book_id=book_id))

        if not title:
            flash("Book title is required.", "danger")
            return redirect(url_for("admin_edit_book", book_id=book_id))

        book.title = title
        book.genre = genre
        book.description = description
        book.price = price
        book.stock = stock
        book.author_id = author_id

        try:
            database.commit()
            flash("Book updated.", "success")
            return redirect(url_for("admin_books"))
        except SQLAlchemyError as error:
            database.rollback()
            flash(f"Database error: {error}", "danger")
    return render_template("admin/book_form.html", book=book, authors=authors)


@app.route("/admin/books/<int:book_id>/delete", methods=["POST"])
def admin_delete_book(book_id):
    database = db()
    book = database.query(Book).filter_by(id=book_id).first()
    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for("admin_books"))
    if book.order_items:
        flash("Cannot delete book because it exists in order history.", "danger")
        return redirect(url_for("admin_books"))
    try:
        database.delete(book)
        database.commit()
        flash("Book deleted.", "success")
    except SQLAlchemyError as error:
        database.rollback()
        flash(f"Database error: {error}", "danger")
    return redirect(url_for("admin_books"))


# ---------------- CUSTOMERS ----------------

@app.route("/admin/customers")
def admin_customers():
    database = db()
    customers = database.query(Customer).order_by(Customer.id.desc()).all()
    return render_template("admin/customers.html", customers=customers)


@app.route("/admin/customers/add", methods=["GET", "POST"])
def admin_add_customer():
    database = db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip() or None
        address = request.form.get("address", "").strip() or None
        if not name or not email:
            flash("Name and email are required.", "danger")
            return redirect(url_for("admin_add_customer"))
        database.add(Customer(name=name, email=email, phone=phone, address=address))
        try:
            database.commit()
            flash("Customer saved.", "success")
            return redirect(url_for("admin_customers"))
        except SQLAlchemyError as error:
            database.rollback()
            flash(f"Database error: {error}", "danger")
    return render_template("admin/customer_form.html", customer=None)


@app.route("/admin/customers/<int:customer_id>/edit", methods=["GET", "POST"])
def admin_edit_customer(customer_id):
    database = db()
    customer = database.query(Customer).filter_by(id=customer_id).first()
    if not customer:
        flash("Customer not found.", "danger")
        return redirect(url_for("admin_customers"))
    if request.method == "POST":
        customer.name = request.form.get("name", "").strip()
        customer.email = request.form.get("email", "").strip()
        customer.phone = request.form.get("phone", "").strip() or None
        customer.address = request.form.get("address", "").strip() or None
        if not customer.name or not customer.email:
            flash("Name and email are required.", "danger")
            return redirect(url_for("admin_edit_customer", customer_id=customer_id))
        try:
            database.commit()
            flash("Customer updated.", "success")
            return redirect(url_for("admin_customers"))
        except SQLAlchemyError as error:
            database.rollback()
            flash(f"Database error: {error}", "danger")
    return render_template("admin/customer_form.html", customer=customer)


@app.route("/admin/customers/<int:customer_id>/delete", methods=["POST"])
def admin_delete_customer(customer_id):
    database = db()
    customer = database.query(Customer).filter_by(id=customer_id).first()
    if not customer:
        flash("Customer not found.", "danger")
        return redirect(url_for("admin_customers"))
    if customer.orders:
        flash("Cannot delete customer with order history.", "danger")
        return redirect(url_for("admin_customers"))
    try:
        database.delete(customer)
        database.commit()
        flash("Customer deleted.", "success")
    except SQLAlchemyError as error:
        database.rollback()
        flash(f"Database error: {error}", "danger")
    return redirect(url_for("admin_customers"))


# ---------------- ORDERS ----------------

@app.route("/admin/orders")
def admin_orders():
    database = db()
    orders = database.query(Order).order_by(Order.id.desc()).all()
    return render_template("admin/orders.html", orders=orders)


@app.route("/admin/orders/<int:order_id>")
def admin_order_detail(order_id):
    database = db()
    order = database.query(Order).filter_by(id=order_id).first()
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("admin_orders"))
    return render_template("admin/order_detail.html", order=order)


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
def admin_update_order_status(order_id):
    database = db()
    order = database.query(Order).filter_by(id=order_id).first()
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("admin_orders"))
    status = request.form.get("status", "Pending")
    allowed = ["Pending", "Processing", "Completed", "Cancelled"]
    if status not in allowed:
        status = "Pending"
    order.status = status
    try:
        database.commit()
        flash("Order status updated.", "success")
    except SQLAlchemyError as error:
        database.rollback()
        flash(f"Database error: {error}", "danger")
    return redirect(url_for("admin_order_detail", order_id=order_id))


# ==========================================================
# RUN APP
# ==========================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
