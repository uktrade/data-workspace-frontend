---
title: Architecture
hide:
  - navigation
---
--8<-- "README.md:architecture"

## Architecture Diagrams

### High Level

At the highest level, users access the Data Workspace application, which accesses a PostgreSQL database.

```mermaid
graph
  A[User] --> B[Data Workspace]
  B --> C["PostgreSQL (Aurora)"]
```
### Medium Level

``` mermaid
graph
  A[User] -->|Staff SSO| B[Amazon Quicksight];
  B --> C["PostgreSQL (Aurora)"];
  A --> |Staff SSO|F["'The Proxy' (aiohttp)"];
  F --> |rstudio-9c57e86a|G[Per-user and shared tools];
  F --> H[Shiny, Flask, Django, NGINX];
  F --> I[Django, Data Explorer];
  G --> C;
  H --> C;
  I --> C;



```
--8<-- "README.md:userfacingcomponents"
--8<-- "README.md:infrastructurecomponents"
--8<-- "README.md:applicationlifecycle"
--8<-- "README.md:customproxy"
--8<-- "README.md:asyncio"
--8<-- "README.md:jupyterhubcomparison"