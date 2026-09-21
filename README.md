## Development

Install the project and development dependencies with `uv sync --extra dev`.

Run the application with:

```sh
uv run haus
```

The initial health check is available at `http://127.0.0.1:8000/health`.

Run the focused test suite with:

```sh
uv run pytest
```

## Raspberry Pi Deployment

Set `HAUS_SESSION_SECRET`, `HAUS_GOOGLE_CLIENT_ID`, and
`HAUS_GOOGLE_CLIENT_SECRET` in the deployment environment, then start the
container stack with `docker compose up -d --build`. Configure the household
router to resolve `haus.home.arpa` to the Pi. Caddy provides the internal TLS
certificate and proxies to the application; each household device must trust
Caddy's internal certificate authority.

Run database migrations inside the application container before a release:

```sh
docker compose run --rm app alembic upgrade head
```
