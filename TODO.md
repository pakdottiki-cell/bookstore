# TODO - Supabase migration

- [x] Update `requirements.txt` to use Postgres driver for Supabase (add `psycopg` / `psycopg2-binary`, remove `PyMySQL`).
- [x] Refactor `app.py` DB config:
- [x] Replace MySQL host/user/password with Supabase env vars (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`).
- [x] Switch SQLAlchemy URL from `mysql+pymysql` to Postgres.
  - [x] Remove MySQL "CREATE DATABASE" logic; just connect and run `Base.metadata.create_all(engine)`.
- [x] Remove/neutralize MySQL-only migration logic in `app.py` (`SHOW COLUMNS...`, `ALTER TABLE ...`).
- [x] Update `app.py` user-facing flash messages to remove “saved in MySQL” wording (optional).
- [x] Update README with Supabase setup + required env vars.
- [ ] Run app locally and verify tables are created & CRUD works.


