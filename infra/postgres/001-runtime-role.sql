-- Purpose: separate runtime data access from the migration owner's DDL privileges.
\getenv runtime_password APP_DATABASE_PASSWORD
CREATE ROLE threatscope LOGIN PASSWORD :'runtime_password';
GRANT CONNECT ON DATABASE threatscope TO threatscope;
GRANT USAGE ON SCHEMA public TO threatscope;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO threatscope;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO threatscope;
