---
title: Deployment
hide:
  - navigation
  - toc
---

Data Workspace is deployed using [Terraform](https://developer.hashicorp.com/terraform/) environments that should sit within a sibling folder to Data Workspace's repository. These environments should then reference the Data Workspace repository's `infra/` folder.

We supply `infra/environment-template/` to allow you to quickly deploy new infrastructure environments. The default platform is AWS, and deploying elsewhere would require significant reconfiguration.

Copy the template files to the repository's sibling directory. We name this `data-workspace-environments` by default.

Let's assume your new environment will be called `deploy`.

```bash
mkdir -p ../data-workspace-environments/deploy && cp -R infra/environment-template/. $_ && cd $_
```

!!! note

    We just changed directory to the newly created `data-workspace-environments/deploy` directory. 
    
    The rest of these instructions assume you are in `data-workspace-environments/deploy`

In the new directory, generate your new SSH keys.

```bash
sh create-keys.sh
```

Enter the details of your hosting platform and SSH keys by changing all instances of `REPLACE_ME` in:

* `admin-environment.json`
* `gitlab-secrets.json`
* `main.tf`

If you haven't already, [install Terraform](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli).

Initialise Terraform.

```bash
terraform init
```

Check the environment you created has worked correctly.

```bash
terraform plan
```

If everything looks right, you're ready to deploy!

```bash
terraform apply
```

## For DBT employees

The above `data-workspace-environments` sibling folder is replaced by the [terraform-data-workspace](https://gitlab.ci.uktrade.digital/data-infrastructure/terraform-data-workspace) repository.

Clone `terraform-data-workspace` as a sibling to the Data Workspace repository, then for each of its environments initialise and apply with Terraform.

```bash
terraform init
terraform apply
```
