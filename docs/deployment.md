---
title: Deployment
hide:
  - navigation
  - toc
---
## Deploying Data Workspace

Within the data-workspace repository, the folder infra-config-template contains terraform files, secrets and keys needed to deploy Data Workspace. Within these files, many IDs, IPs, secrets and tokens need to be replaced. After doing so, run the following commands whilst checked out to the infra-config-template folder:

```bash
terraform init
terraform apply
```