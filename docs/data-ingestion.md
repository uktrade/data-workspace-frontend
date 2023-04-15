---
title: Data Ingestion
hide:
  - navigation
---

Data Workspace is essentially an interface to a PostgreSQL database, referred to as the datasets database. Technical users can access specific tables in the datasets database directly, but there is a concept of "datasets" on top of this direct access. Each dataset has its own page in the user-facing data catalogue that has features for non-technical users.

Conceptually, there are 3 different types of datasets in Data Workspace: source datasets, reference datasets, and data cuts. Metadata for the 3 dataset types is controlled through a single administration interface, but how data is ingested into these depends on the dataset.


## Metadata

Data Workspace is a [Django](https://www.djangoproject.com/) application, with a staff-facing administration interface, usually refered to as Django admin. Metadata for of each the 3 types of dataset is managed within Django admin.


## Source datasets

A source dataset is the core Data Workspace dataset type. It is made up of one or more tables in the datasets database. Typically a source dataset would be updated frequently.

However, ingesting into these tables is not handled by the Data Workspace project itself. There are many ways to data into a source dataset. The Department for Business and Trade uses [Airflow](https://airflow.apache.org/) to handle ingestion using a combination of Python and SQL code.

!!! note

    The Airflow pipelines used by The Department for Business and Trade to ingest data are not open source. Some parts of Data Workspace relating to this ingestion depend on this closed source code.


## Reference datasets

Reference datasets are datasets usually used to classify or contextualise other datasets, and are expected to not change frequently. "UK bank holidays" or "ISO country codes" could be reference datasets.

The structure and data of reference datasets can be completely controlled through Django admin.


## Data cuts

Data isn't ingested into data cuts directly. Instead, data cuts are defined by SQL queries entered into Django admin that run dynamically, querying from source and reference datasets. As such they update as frequently as the data they query from updates.

A datacut could filter a larger source dataset for a specific country, calculate aggregate statistics, join multiple source datasets together, join a source dataset with a reference dataset, or a combination of these.
