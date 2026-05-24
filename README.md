# supermarket

MCP server for Irish supermarket product search. An LLM client can search products and assemble a shopping list across stores, with each store reached through [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) to clear its bot protection.

## Stores

Pick a store with the `store` argument on each tool.

| `store` | Site | Protection | Session model |
| --- | --- | --- | --- |
| `dunnes` (default) | dunnesstoresgrocery.com | Cloudflare | Bootstrap cookies once, then plain `requests`. Recycled after `MCP_SESSION_TTL`. |
| `supervalu` | shop.supervalu.ie | Cloudflare | Same as Dunnes (identical storefront platform). |
| `aldi` | aldi.ie | Bot block | Same cookie-reuse model as Dunnes, but its own URL scheme and `product-tile` DOM. |
| `tesco` | tesco.ie | Akamai | Every search fetched through FlareSolverr (Akamai validates per request). |
| `lidl` | lidl.ie | JS-rendered | Every search fetched through FlareSolverr (the product grid is rendered client-side). |

## How it works

Each store owns its own session. **Dunnes**, **SuperValu**, and **Aldi** share one cookie-reuse model: each bootstraps a FlareSolverr browser session, harvests the cookies + user-agent, and reuses them with plain `requests`. FlareSolverr is only re-invoked on a challenge (expired cookie) or when the session ages past `MCP_SESSION_TTL`. Dunnes and SuperValu run the same storefront platform (only host + retailer id differ). Aldi reuses the same session lifecycle but has its own URL scheme and `product-tile` DOM. **Tesco** and **Lidl** can't reuse cookies. Tesco's Akamai validates per request, and Lidl renders its grid client-side. So they fetch every results page through FlareSolverr. Either way, cookies/sessions are bound to the FlareSolverr host's IP, so the server must share that outbound IP.

SuperValu's search is stricter than the others: a long query with pack-size tokens (`Volvic Natural Mineral Water 6 x 1.5l`) often matches nothing, while the trimmed query (`Volvic`) returns the full grid. To cope, the cookie-reuse stores retry once on an empty result with the size tokens stripped (`12 x 330ml`, `2L`, `1000g`, `48 washes`, ...), then let the caller pick the right pack from the broadened candidates. The retry only fires when the literal query returned nothing, so it never narrows a query that already worked. It can't rescue every case (a non-size word like "Jar" can still throw the search off), so refine the query if a known product comes back empty.

## FlareSolverr

Every store reaches its site through a running FlareSolverr instance. Run it as a container with either Docker or Podman.

The same compose file works for both, only the command differs: `docker compose up -d` versus `podman-compose up -d`.

```yaml
services:
  flaresolverr:
    image: ghcr.io/flaresolverr/flaresolverr:latest
    container_name: flaresolverr
    ports:
      - 8191:8191
    environment:
      - LOG_LEVEL=info
    restart: unless-stopped
```

For a one-off run the command is identical under both. Use `docker run` or `podman run` the same way:

```bash
docker run -d --name flaresolverr -p 8191:8191 \
  -e LOG_LEVEL=info --restart unless-stopped \
  ghcr.io/flaresolverr/flaresolverr:latest

# or

podman run -d --name flaresolverr -p 8191:8191 \
  -e LOG_LEVEL=info --restart unless-stopped \
  ghcr.io/flaresolverr/flaresolverr:latest
```

Then point the server at it with `FLARESOLVERR_URL` (below). If you do put FlareSolverr on another host or network, set `FLARESOLVERR_URL` to that address (and recall the IP-binding caveat above).

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `FLARESOLVERR_URL` | `http://127.0.0.1:8191/v1` | FlareSolverr endpoint. |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http`. |
| `MCP_HOST` | `127.0.0.1` | HTTP bind host (streamable-http only). |
| `MCP_PORT` | `8765` | HTTP bind port (streamable-http only). |
| `MCP_SESSION_TTL` | `3600` | Cookie-reuse store (Dunnes/SuperValu/Aldi) session lifetime in seconds before recycling. |

## Tools

| Tool | Arguments | Returns |
| --- | --- | --- |
| `search_product` | `query: str`, `store: str = "dunnes"`, `limit: int = 10` | `{query, store, found, candidates}`. Candidates in the store's relevance order. The caller picks the right one. |
| `build_shopping_list` | `queries: list[str]`, `store: str = "dunnes"`, `limit: int = 10` | A list of per-query `{query, store, found, candidates}` dicts, in input order. |

Each candidate has `name`, `price`, `clubcard_price`, `was`, `discount`, `unit_price`, `available`, and `url`. `price` is the unconditional price.  `clubcard_price` is Tesco's loyalty price for a simple per-unit deal (`null` for the other stores and for multibuy offers, which stay described in `discount`). Lidl's advertised price already reflects any Lidl Plus discount, with the deal text kept in `discount`.

## Running

```bash
uv sync
uv run supermarket-mcp                                   # stdio (default)
MCP_TRANSPORT=streamable-http MCP_PORT=8765 uv run supermarket-mcp   # HTTP
```

The HTTP endpoint is served at `/mcp` (e.g. `http://<MCP_HOST>:<MCP_PORT>/mcp`).

### As a container

The `Dockerfile` builds an image that runs the server over streamable HTTP on port 8765 (`MCP_HOST` defaults to `0.0.0.0` so it's reachable from outside the container). Works the same under Docker or Podman:

```bash
docker build -t supermarket-mcp .
docker run -d --name supermarket-mcp -p 8767:8765 \
  -e FLARESOLVERR_URL=http://127.0.0.1:8191/v1 \
  supermarket-mcp

# or

podman build -t supermarket-mcp .
podman run -d --name supermarket-mcp -p 8767:8765 \
  -e FLARESOLVERR_URL=http://127.0.0.1:8191/v1 \
  supermarket-mcp
```

### With Compose

Build the image first:

```bash
docker build -t supermarket-mcp .

# or

podman build -t supermarket-mcp .
```

Then reference that pre-built image from `compose.yaml`:

```yaml
services:
  supermarket-mcp:
    image: supermarket-mcp
    container_name: supermarket-mcp
    restart: unless-stopped
    ports:
      - "8767:8765"
    environment:
      # Harvested cookies are IP-bound, so this must share FlareSolverr's
      # outbound IP. Run it on the same host as FlareSolverr (shared NAT egress).
      FLARESOLVERR_URL: "${FLARESOLVERR_URL:-http://127.0.0.1:8191/v1}"
      MCP_TRANSPORT: streamable-http
      MCP_HOST: 0.0.0.0
      MCP_PORT: "8765"
      MCP_SESSION_TTL: "${MCP_SESSION_TTL:-3600}"
```

Bring it up with `docker compose up -d` or `podman-compose up -d`. The MCP endpoint is then on the host at `http://<host>:8767/mcp`. Override `FLARESOLVERR_URL` (and optionally `MCP_SESSION_TTL`) in the environment or a `.env` file rather than editing the YAML.

Because harvested cookies are bound to FlareSolverr's outbound IP, run this container on the **same host as FlareSolverr** so they share a NAT egress. Otherwise the cookie-reuse stores (Dunnes/SuperValu/Aldi) will be challenged on every request. Point `FLARESOLVERR_URL` at your FlareSolverr instance.

## Client configuration

Stdio (the client spawns the server):

```json
{
  "mcpServers": {
    "supermarket": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/supermarket", "supermarket-mcp"],
      "env": { "FLARESOLVERR_URL": "http://127.0.0.1:8191/v1" }
    }
  }
}
```

Streamable HTTP (the server runs separately, the client connects by URL):

```json
{
  "mcpServers": {
    "supermarket": { "url": "http://127.0.0.1:8765/mcp" }
  }
}
```

Or register it with the Claude Code CLI:

```sh
claude mcp add --transport http supermarket http://<host>:8765/mcp
```

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run bandit -r supermarket_mcp
uv run pytest -v tests/ --cov
# live round-trip. Spawns the server itself, needs FlareSolverr reachable at FLARESOLVERR_URL
FLARESOLVERR_URL=http://127.0.0.1:8191/v1 uv run python scripts/smoke.py "milk" --store tesco --limit 3
```

Layout: `supermarket_mcp/server.py` (FastMCP app + tools), `flaresolverr.py` and `helpers.py` (shared), and one module per store under `supermarket_mcp/stores/`. Stores share one of two session bases: cookie-reuse stores (Dunnes, SuperValu, Aldi) extend `CookieReuseStore` in `stores/_cookie_reuse.py`. Per-request FlareSolverr stores (Tesco, Lidl) extend `FlareSolverrStore` in `stores/_flaresolverr_store.py`. To add a store, implement the `Store` protocol from `stores/base.py`. Usually by extending the base that matches its protection (supply the home/search URL and parser). And register it in `server.STORES`.

## License

This project is licensed under the [MIT License](LICENSE).
