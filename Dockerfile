FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY supermarket_mcp/ ./supermarket_mcp/
RUN uv sync --frozen --no-dev

EXPOSE 8765

ENV MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8765

CMD ["/app/.venv/bin/supermarket-mcp"]
