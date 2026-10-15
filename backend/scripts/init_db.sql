-- Runs once, when the Postgres volume is first created (docker-entrypoint-initdb.d).
-- Enables pgvector in the main database and creates the test database used by `make test`.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE DATABASE syncra_test;
\connect syncra_test
CREATE EXTENSION IF NOT EXISTS vector;
