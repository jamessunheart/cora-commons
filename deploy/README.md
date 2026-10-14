# Hosted MCP deployment

The public endpoint is a stateless Streamable HTTP service behind the existing FullPotential.com nginx proxy.

- Service user: `cora-mcp` (no login, no private credentials)
- Application: `/opt/cora-commons-mcp/current`
- Loopback listener: `127.0.0.1:8840`
- Public endpoint: `https://fullpotential.com/mcp`
- Public authority: read, explain, search, match, draft and validate only
- Collaboration record: GitHub issues, forks and pull requests

Production must use the included systemd hardening, request-size limit, per-IP rate limit and nginx TLS proxy. Before reloading nginx, back up its current configuration and run `nginx -t`. Verify deployment with a real MCP client that initializes, lists tools/resources and calls `understand_commons`; a browser GET is not sufficient proof.

## Production Python boundary

The service uses `ProtectHome=true`, so its virtual environment must not link to an interpreter under `/root`, a login home or a transient build cache. Install or reuse a pinned interpreter under `/opt/cora-commons-mcp/python`, then pass its absolute path when creating each release environment:

```bash
uv sync --python /opt/cora-commons-mcp/python/cpython-3.11.14-linux-x86_64-gnu/bin/python3.11 --frozen --no-dev
```

Before switching `current`, verify `.venv/bin/python` resolves beneath `/opt/cora-commons-mcp`, run the complete test suite, and start the service. A root-run test is insufficient because root may access paths denied to the hardened `cora-mcp` service user.

Rollback disables the service, restores the timestamped nginx configuration, removes the rate-limit include, validates nginx and reloads it. Application releases remain under `/opt/cora-commons-mcp/releases` for inspection.
