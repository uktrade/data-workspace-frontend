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

## Deploying Data Workspace (ideal)

Data Workspace is deployed using [Terraform](https://developer.hashicorp.com/terraform), and this repo contains templates to allow you to quickly deploy new infrastructure environments.

Set up your new environment by cloning the sample environment .env file.

For security, this new .env file will need adding to the .gitignore. Any .env file in .env/terraform/ will be ignored by default.

```bash
cp .env/sample_terraform_environment.env .env/terraform/my_environment.env
# add .env/terraform/ to .gitignore
```

Edit your new environment's .env file, entering the details of your hosting platform.

You're ready to create the new environment's configuration files. There's a make command just for this.

```bash
make terraform_environments
# add infra/environment to .gitignore

# Using infra/environment_template, creates infra/environment/my_environment/ using the my_environment.env settings
# Will do the same for anything in .env/terraform
# Note that environment_template's sources will now be within this repo, and will need updating
# Make a way to diff ci.uktrade.digital's version with our template? Idk.
```

`make terraform_environments` creates any environment in .env/terraform/ in infra/environment/. It creates a directory based on the `TERRAFORM_DIR_NAME` variable you set.

For security, this environment configuration folder will need adding to the .gitignore. Anything in infra/environment/ is ignored by default.

Let's assume you set `TERRAFORM_DIR_NAME=my_environment`. Go to your new directory and initialise Terraform.

```bash
cd infra/environment/my_environment
terraform init
# add .terraform to .gitignore
```

Check the environment your created has worked correctly.

```bash
terraform plan
```

If everything looks right, you're ready to deploy!

```bash
terraform apply
```
