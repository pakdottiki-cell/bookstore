BOOKSTORE CUSTOMER + ADMIN WEB APP
Flask + SQLAlchemy ORM + MySQL Workbench

SETUP:
1. Open app.py.
2. Edit MYSQL_USER and MYSQL_PASSWORD near the top if needed.
   XAMPP default is usually:
       MYSQL_USER = "root"
       MYSQL_PASSWORD = ""
3. Make sure MySQL Server is running.
4. Install packages:
       python -m pip install -r requirements.txt
5. Run:
       python app.py
6. Open browser:
       http://127.0.0.1:5000

DATABASE:
- The app automatically creates database bookstore_db if it does not exist.
- The app automatically creates all tables.

MYSQL WORKBENCH CHECK:
USE bookstore_db;
SHOW TABLES;
SELECT * FROM authors;
SELECT * FROM books;
SELECT * FROM customers;
SELECT * FROM orders;
SELECT * FROM order_items;

MAIN PAGES:
Customer shop:
    /
    /shop
    /cart
    /checkout

Admin pages:
    /admin
    /admin/authors
    /admin/books
    /admin/customers
    /admin/orders
