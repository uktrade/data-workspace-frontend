---
title: Data Ingestion
hide:
  - navigation
---
## Getting Data Into Data Workspace

Data Workspace stores 3 dataset types in a PostgreSQL database: Source datasets, Datacuts and Reference datasets.

- A source dataset is made up of one or more tables in the database, in any schemas. These are the core datasets that are used with Data Workspace's tools for analysis, for example a table containing records ingested from publicly available Companies House accounts data.

- Reference datasets are more general datasets, for example "UK bank holidays", that can be useful in combination with and to contextualise source datasets. These can also be ingested into Data Workspace using Django Admin

- Datacuts are subsets of data, often created by SQL queries on source datasets in order to segment data. These are often subsets according to dates or regions, for example splitting a dataset relating to the United Kingdom into data cuts for each constituent country.

Ingesting into these tables is for the most part not handled by the Data Workspace project itself. There are many options for ways that you could ingest data yourself. We use Apache Airflow for orchestration but other options are available.

!!! note

    A combination of pipeline code and Apache Airflow is used internally to transfer data into the Data Workspace PostgreSQL database, but the code for these DAGs is not open source.
