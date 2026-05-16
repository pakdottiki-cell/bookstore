"""
Bookstore Web App
Customer Ordering + Admin Management
Flask + SQLAlchemy ORM + Supabase PostgreSQL

Before running:

pip install flask sqlalchemy psycopg psycopg-binary python-dotenv

Create a .env file:

DATABASE_URL=postgresql+psycopg://postgres.PROJECT_REF:PASSWORD@aws-1-ap-south-1.pooler.supabase.com:6543/postgres
SECRET_KEY=bookstore-secret-key

Run:
python app.py
"""

import os
from datetime import datetime
from decimal import Decimal, InvalidOperation

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Numeric,
    ForeignKey,
    DateTime,
)
from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
    scoped_session,
    relationship,
)
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

# ==========================================================
# LOAD ENVIRONMENT VARIABLES
# ==========================================================

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing in .env")

# ==========================================================
# FLASK SETUP
# ==========================================================

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ==========================================================
# DATABASE SETUP
# ==========================================================

Base = declarative_base()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
)

DBSession = scoped_session(sessionmaker(bind=engine))

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
    order_items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )


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
# CREATE TABLES
# ==========================================================

try:
    Base.metadata.create_all(engine)
    print("Connected to Supabase PostgreSQL.")
    print("Database tables created successfully.")
except SQLAlchemyError as error:
    print("Database connection failed.")
    print(error)
    raise SystemExit

# ==========================================================
# HELPERS
# ==========================================================

def db():
    return DBSession()


@app.teardown_appcontext
def remove_session(exception=None):
    DBSession.remove()


def get_cart_items(database):
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


@app.context_processor
def inject_cart_count():
    cart = session.get("cart", {})
    count = sum(cart.values()) if cart else 0
    return {"cart_count": count}

# ==========================================================
# SHOP ROUTES
# ==========================================================

@app.route("/")
def home():
    database = db()

    books = (
        database.query(Book)
        .filter(Book.stock > 0)
        .order_by(Book.id.desc())
        .limit(6)
        .all()
    )

    return render_template("shop/home.html", books=books)


@app.route("/shop")
def shop():
    database = db()

    keyword = request.args.get("q", "").strip()

    query = database.query(Book).filter(Book.stock > 0)

    if keyword:
        query = query.filter(Book.title.like(f"%{keyword}%"))

    books = query.order_by(Book.title).all()

    return render_template(
        "shop/shop.html",
        books=books,
        keyword=keyword,
    )


@app.route("/book/<int:book_id>")
def book_detail(book_id):
    database = db()

    book = database.query(Book).filter_by(id=book_id).first()

    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for("shop"))

    return render_template(
        "shop/book_detail.html",
        book=book,
    )


@app.route("/cart")
def cart():
    database = db()

    items, total = get_cart_items(database)

    return render_template(
        "shop/cart.html",
        items=items,
        total=total,
    )


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
        flash("Not enough stock.", "danger")
        return redirect(url_for("book_detail", book_id=book_id))

    cart[str(book_id)] = current_qty + quantity

    session["cart"] = cart

    flash("Book added to cart.", "success")

    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    database = db()

    items, total = get_cart_items(database)

    if not items:
        flash("Cart is empty.", "warning")
        return redirect(url_for("shop"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not name or not email or not address:
            flash("Please complete required fields.", "danger")
            return redirect(url_for("checkout"))

        customer = Customer(
            name=name,
            email=email,
            phone=phone,
            address=address,
        )

        order = Order(
            customer=customer,
            status="Pending",
        )

        database.add(customer)
        database.add(order)

        for item in items:

            book = item["book"]
            qty = item["quantity"]

            if qty > book.stock:
                flash(f"Not enough stock for {book.title}", "danger")
                return redirect(url_for("cart"))

            book.stock -= qty

            order_item = OrderItem(
                order=order,
                book=book,
                quantity=qty,
                unit_price=book.price,
            )

            database.add(order_item)

        try:
            database.commit()

            session["cart"] = {}

            flash("Order placed successfully.", "success")

            return redirect(
                url_for(
                    "order_success",
                    order_id=order.id,
                )
            )

        except SQLAlchemyError as error:
            database.rollback()

            flash(f"Database error: {error}", "danger")

            return redirect(url_for("checkout"))

    return render_template(
        "shop/checkout.html",
        items=items,
        total=total,
    )


@app.route("/order-success/<int:order_id>")
def order_success(order_id):
    database = db()

    order = database.query(Order).filter_by(id=order_id).first()

    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("shop"))

    return render_template(
        "shop/order_success.html",
        order=order,
    )

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


@app.route("/admin/authors")
def admin_authors():
    database = db()

    authors = database.query(Author).order_by(Author.name).all()

    return render_template(
        "admin/authors.html",
        authors=authors,
    )


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

            flash("Author added.", "success")

            return redirect(url_for("admin_authors"))

        except IntegrityError:
            database.rollback()

            flash("Author already exists.", "danger")

    return render_template(
        "admin/author_form.html",
        author=None,
    )

# ==========================================================
# RUN APP
# ==========================================================

if __name__ == "__main__":
    app.run(debug=True)