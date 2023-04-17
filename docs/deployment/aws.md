---
title: Deploying to AWS
---
# Deploying to AWS

Data Workspace contains code that helps it be deployed using Amazon Web Services (AWS). This page explains how to use this code.


## Prerequisites

To deploy Data Workspace to AWS you must have:

- The source code of Data Workspace cloned to a folder `data-workspace`. See [Running locally](../development/running-locally.md) for details
- An [AWS](https://aws.amazon.com/) account
- [Terraform](https://developer.hashicorp.com/terraform/) installed
- An OAuth 2.0 server for authentication

You should also have familiarity with working on the command line, working with Terraform, and with AWS.


## Environment folder

Each deployment, or environment, of Data Workspace requires a folder for its configuration. This folder should be within a sibling folder to `data-workspace`.

The Data Workspace source code contains a template for this configuration. To create a folder in an appropriate location based on this template:

1. Decide on a meaningful name for the environment. In the following `production` is used.

2. Ensure you're in the root of the `data-workspace` folder that contains the cloned Data Workspace source code.

3. Copy the template into a new folder for the environment

    ```bash
    mkdir -p ../data-workspace-environments
    cp -R infra/environment-template ../data-workspace-environments/production
    ```

This folder structure allows the configuration to find and use the `infra/` folder in `data-workspace` which contains the low level details of the infrastructure to provision in each environment.


## Initialising environment

Before deploying the environment, it must be initialised.


1. Change to the new folder for the environment

    ```bash
    cd ../data-workspace-environments/production
    ```

2. Generate new SSH keys.

    ```bash
    sh create-keys.sh
    ```

2. Enter the details of your hosting platform, SSH keys, and OAuth 2.0 server by changing all instances of `REPLACE_ME` in:

    * `admin-environment.json`
    * `gitlab-secrets.json`
    * `main.tf`

3. Initialise Terraform.

    ```bash
    terraform init
    ```


## Deploying environment

Check the environment you created has worked correctly.

```bash
terraform plan
```

If everything looks right, you're ready to deploy!

```bash
terraform apply
```
