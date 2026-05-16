BOOKSTORE CUSTOMER + ADMIN WEB APP
Flask + SQLAlchemy ORM + Supabase Postgres

SETUP (Supabase):
1. Create a Supabase project.
2. Get these values from Supabase Project Settings -> Database -> Connection string info:
   - SUPABASE_URL (REST URL, e.g. https://xxxx.supabase.co)
   - SUPABASE_SERVICE_ROLE_KEY (service role secret)
3. Local development (.env):
   - Create a `.env` file in this project directory with:
       SUPABASE_URL=...
       SUPABASE_SERVICE_ROLE_KEY=...
   - (Optional) You can also set them in your shell/terminal.
4. Install packages:

       python -m pip install -r requirements.txt
5. Run:
       python app.py
6. Open browser:
       http://127.0.0.1:5000

DATABASE:
- On startup, the app creates the tables from ORM models in your Supabase Postgres database.

Notes:
- This app uses the Service Role key for server-side DB access.
- If you want RLS/policy-based access from the client, that requires a different approach (not used here).


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
