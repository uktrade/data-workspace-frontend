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

3. Copy the template into a new folder for the environment:

    ```bash
    mkdir -p ../data-workspace-environments
    cp -Rp infra/environment-template ../data-workspace-environments/production
    ```

This folder structure allows the configuration to find and use the `infra/` folder in `data-workspace` which contains the low level details of the infrastructure to provision in each environment.


## Initialising environment

Before deploying the environment, it must be initialised.


1. Change to the new folder for the environment:


    ```bash
    cd ../data-workspace-environments/production
    ```

2. Generate new SSH keys:

    ```bash
    ./create-keys.sh
    ```

3. [Install AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) and [configure an AWS CLI profile](https://docs.aws.amazon.com/toolkit-for-visual-studio/latest/user-guide/keys-profiles-credentials.html). This will support some of the included configuration scripts.

    You can do this by putting credentials directly into `~/.aws/credentials` or by using `aws sso`.

4. Create an S3 bucket and dynamodb table for Terraform to use, and add them to `main.tf`. `--bucket` will provide the base name for both objects.

    ```bash
    ./bootstrap-terraform.sh \
        --profile <value> \
        --bucket <value> \
        --region <value>
    ```

5. Enter the details of your hosting platform, SSH keys, and OAuth 2.0 server by changing all instances of `REPLACE_ME` in:

    * `admin-environment.json`
    * `gitlab-secrets.json`
    * `main.tf`

3. Initialise Terraform:

    ```bash
    terraform init
    ```


## Deploying environment

Check the environment you created has worked correctly:

```bash
terraform plan
```

If everything looks right, you're ready to deploy:

```bash
terraform apply
```
