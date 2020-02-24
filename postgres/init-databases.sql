CREATE DATABASE dataworkspace;
CREATE DATABASE datasets;

CREATE DATABASE testdb1;
CREATE DATABASE testdb2;

\c datasets;
CREATE TABLE test_dataset (id int primary key, data text);
INSERT INTO test_dataset VALUES (1, 'test data 1');
INSERT INTO test_dataset VALUES (2, 'test data 2');

\c testdb1;
CREATE TABLE dataset_1 (id int primary key, data text);
INSERT INTO dataset_1 VALUES (1, 'test data 1');
INSERT INTO dataset_1 VALUES (2, 'test data 2');

\c testdb2;
CREATE TABLE dataset_2 (id int primary key, data text);
INSERT INTO dataset_2 VALUES (1, 'test data 1');
INSERT INTO dataset_2 VALUES (2, 'test data 2');
