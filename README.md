# Data Workspace [![CircleCI](https://circleci.com/gh/uktrade/data-workspace.svg?style=svg)](https://circleci.com/gh/uktrade/data-workspace)

Allows users to launch applications in order to analyse data

![Data Workspace architecture](data-workspace-architecture.png)

## Running locally

Set the required variables by

```bash
cp analysis-workspace.env .env
```

and edit `.env`, specifically replacing `AUTHBROKER_*`. Start the application by

```bash
docker-compose up --build
```

With the default environment, you will need the below in your `/etc/hosts` file.

```
127.0.0.1       localapps.com
```

And the application will be visible at http://localapps.com. This is to be able to properly test cookies that are shared with subdomains.


## Creating migrations / running management commands

```bash
docker-compose build && \
docker-compose run \
    --user root \
    --volume=$PWD/app/app/migrations:/app/app/migrations \
    data-workspace django-admin makemigrations
```

For other commands, replace `makemigrations` with the name of the command.


## Running tests

```bash
docker-compose build data-workspace && \
docker-compose -f docker-compose-test.yml build && \
docker-compose -f docker-compose-test.yml run data-workspace-test python3 -m unittest test.test
```

Django tests
```bash
docker-compose -f docker-compose-test.yml run data-workspace-test django-admin test /dataworkspace/dataworkspace
```


# Infrastructure

The infrastructure is heavily Docker/Fargate based. Production Docker images are built by [quay.io](https://quay.io/organization/uktrade).


## User-facing components

- [Main application](https://quay.io/repository/uktrade/data-workspace)
  A Django application to manage datasets and permissions, launch containers, a proxy to route requests to those containers, and an NGINX instance to route to the proxy and serve static files.

- [JupyterLab](https://quay.io/repository/uktrade/data-workspace-jupyterlab)
  Launched by users of the main application, and populated with credentials in the environment to access certain datasets.

- [rStudio](https://quay.io/repository/uktrade/data-workspace-rstudio)
  Launched by users of the main application, and populated with credentials in the environment to access certain datasets.

- [pgAdmin](https://quay.io/repository/uktrade/data-workspace-pgadmin)
  Launched by users of the main application, and populated with credentials in the environment to access certain datasets.


## Infrastructure components

- [metrics](https://quay.io/repository/uktrade/data-workspace-metrics)
  A sidecar-container for the user-launched containers that exposes metrics from the [ECS task metadata endpoint](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-metadata-endpoint-v3.html) in Prometheus format.

- [s3sync](https://quay.io/repository/uktrade/data-workspace-s3sync)
  A sidecar-container for the user-launched containers that syncs to and from S3 using [mobius3](https://github.com/uktrade/mobius3). This is to allow file-persistance on S3 without using FUSE, which at the time of writing is not possible on Fargate.

- [dnsmasq](https://quay.io/repository/uktrade/data-workspace-dnsmasq)
  The DNS server of the VPC that launched containers run in. It selectivly allows only certain DNS requests through to migitate chance of data exfiltration through DNS. When this container is deployed, it changes DHCP settings in the VPC, and will most likely break aspects of user-launched containers.

- [healthcheck](https://quay.io/repository/uktrade/data-workspace-healthcheck)
  Proxies through to the healthcheck endpoint of the main application, so the main application can be in a security group locked-down to certain IP addresses, but still be monitored by Pingdom.

- [mirrors-sync](https://quay.io/repository/uktrade/data-workspace-mirrors-sync)
  Mirrors pypi, CRAN and (ana)conda repositories to S3, so user-launched JupyterLab and rStudio containers can install packages without having to contact the public internet.

- [prometheus](https://quay.io/repository/uktrade/data-workspace-prometheus)
  Collects metrics from user-launched containers and re-exposes them through federation.

- [registry](https://quay.io/repository/uktrade/data-workspace-registry)
  A Docker pull-through-cache to repositories in [quay.io](https://quay.io/organization/uktrade). This allows the VPC to not have public internet access but still launch containers from quai.io in Fargate.

- [sentryproxy](https://quay.io/repository/uktrade/data-workspace-sentryproxy)
  Proxies errors to a Sentry instance: only used by JupyterLab.


## Why the custom proxy?

A common question is why not just NGINX instead of the custom proxy? The reason is the dynamic routing for the applications, e.g. URLs like https://jupyterlab-abcde1234.mydomain.com/: each one has a lot of fairly complex requirements.

- It must redirect to SSO if not authenticated, and redirect back to the URL once authenticated.
- It must perform ip-filtering that is not applicable to the main application.
- It must check that the current user is allowed to access the application, and show a forbidden page if not.
- It must start the application if it's not started.
- It must show a starting page with countdown if it's starting.
- It must detect if an application has started, and route requests to it if it is.
- It must route cookies from _all_ responses back to the user. For JupyterLab, the _first_ response contains cookies used in XSRF protection that are never resent in later requests.
- It must show an error page if there is an error starting or connecting to the application.
- It must allow a refresh of the error page to attempt to start the application again.
- It must support WebSockets, without knowledge ahead of time which paths are used by WebSockets.
- It must support streaming uploads and downloads.
- Ideally, there would not be duplicate reponsibilities between the proxy and other parts of the system, e.g. the Django application.

While not impossible to leverage NGINX to move some code from the proxy, there would still need to be custom code, and NGINX would have to communicate via some mechanism to this custom code to acheive all of the above: extra HTTP or Redis requests, or maybe through a custom NGINX module. It is suspected that this will make things more complex rather than less, and increase the burden on the developer.
