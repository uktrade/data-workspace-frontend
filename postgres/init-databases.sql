CREATE DATABASE dataworkspace;
CREATE DATABASE datasets;

CREATE DATABASE testdb1;
CREATE DATABASE testdb2;

\c datasets;
CREATE TABLE test_dataset (id int primary key, data text);
INSERT INTO test_dataset(id, data)
SELECT i, concat('test data ', i::text)
FROM generate_series(1, 20000) AS t(i);
CREATE SCHEMA dataflow;
CREATE TABLE dataflow.metadata
(
    id SERIAL NOT NULL CONSTRAINT metadata_pkey PRIMARY KEY,
    table_schema TEXT NOT NULL,
    table_name TEXT NOT NULL,
    source_data_modified_utc TIMESTAMP,
    dataflow_swapped_tables_utc TIMESTAMP NOT NULL
);

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
