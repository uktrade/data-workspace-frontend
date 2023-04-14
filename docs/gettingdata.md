---
title: Getting Data into Data Workspace
hide:
  - navigation
---
## Getting Data Into Data Workspace

Data Workspace stores 3 dataset types in a PostgreSQL database: Source datasets, Datacuts and Reference datasets.

- A source dataset is one or more tables in the database, in any schemas

- Reference datasets can be ingested in Data Workspace using Django Admin

- Datacuts are subsets of data, often created by SQL queries

Ingesting into these tables is for the most part not handled by the Data Workspace project itself. There are many options for ways that you could ingest data yourself.

!!! note

    A combination of pipeline code and [Apache Airflow](https://airflow.apache.org/) is used internally to transfer data into the Data Workspace PostgreSQL database, but the code for these DAGs is not open source.