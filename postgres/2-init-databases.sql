CREATE EXTENSION pgaudit;
ALTER SYSTEM SET pgaudit.log = 'none';
CREATE ROLE rds_pgaudit;

CREATE DATABASE dataworkspace;
CREATE DATABASE datasets;
CREATE DATABASE airflow;
CREATE DATABASE superset;

CREATE DATABASE testdb1;
CREATE DATABASE testdb2;

\c datasets;
CREATE TABLE test_dataset (id int primary key, data text);
INSERT INTO test_dataset(id, data)
SELECT i, concat('test data ', i::text)
FROM generate_series(1, 20000) AS t(i);
CREATE SCHEMA dataflow;
CREATE SCHEMA _data_explorer_charts;

\c testdb1;
CREATE TABLE dataset_1 (id int primary key, data text);
INSERT INTO dataset_1(id, data)
SELECT i, concat('test data ', i::text)
FROM generate_series(1, 2) AS t(i);

\c testdb2;
CREATE TABLE dataset_2 (id int primary key, data text);
INSERT INTO dataset_2(id, data)
SELECT i, concat('test data ', i::text)
FROM generate_series(1, 2) AS t(i);
