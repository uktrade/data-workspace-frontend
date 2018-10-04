# jupyterhub-data-auth-admin

Application that controls authorisation for data sources accessed from JupyterHub

## Running locally

```bash
docker build . -t jupyterhub-data-auth-admin && \
docker run --rm -it -p 8000:8000 -e SECRET_KEY=something-secret jupyterhub-data-auth-admin
```
