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

Data Workspace is deployed using [Terraform](https://developer.hashicorp.com/terraform), and this repo contains templates to allow you to quickly deploy new infrastructure environments. The default platform is AWS, and deploying elsewhere would require significant reconfiguration.

`make terraform_environments` prompts you to name a new environment, then creates it in infra/environment/. It generates the required SSH keys, confgures as much of the environment's terraform.tfvars file as possible, and initialises Terraform in the new directory.

For security, the generated environment configuration folder will need adding to the .gitignore. Anything in infra/environment/ is ignored by default.

```bash
make terraform_environments
# add infra/environment to .gitignore
# add terraform.tfvars to infra/environment_template

# Prompts for a new environment name, eg deploy, refuses if it exists
# Using infra/environment_template, creates infra/environment/deploy/
# cd to new directory
# runs terraform init
# generates the ssh keys and adds to terraform.tfvars
# cd back to root

# Note that environment_template's source params will now reference this repo, and will need updating
# Make a way to diff ci.uktrade.digital's version with our template? Idk.
```

Let's assume you named your new environment `deploy`.

```bash
cd infra/environment/deploy
```

Edit your new environment's terraform.tfvars file, entering the details of your hosting platform.

Check the environment you created has worked correctly.

```bash
terraform plan
```

If everything looks right, you're ready to deploy!

```bash
terraform apply
```
