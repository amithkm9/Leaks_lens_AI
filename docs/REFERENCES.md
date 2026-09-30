# Implementation references

Official documentation consulted while implementing this build. Lockfiles record the versions actually installed; these links may describe newer versions.

- [FastAPI security and password hashing](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [SQLAlchemy 2 ORM](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)
- [Alembic migrations](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [RQ workers and queues](https://python-rq.org/docs/)
- [Gitleaks repository and CLI](https://github.com/gitleaks/gitleaks), [pinned release](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1)
- [Presidio analyzer](https://presidio.dataprivacystack.org/analyzer/)
- [pypdf extraction limits and behavior](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)
- [FastMCP client transports](https://gofastmcp.com/clients/transports)
- [LangGraph StateGraph](https://reference.langchain.com/python/langgraph/graph/state/StateGraph)
- [Anthropic Messages API](https://platform.claude.com/docs/en/api/messages/create)
- [Git configuration and curl resolve pinning](https://git-scm.com/docs/git-config)
- [Vite guide](https://vite.dev/guide/)
- [Tailwind Vite integration](https://tailwindcss.com/docs/installation/using-vite)
- [Radix accessible dialog primitives](https://www.radix-ui.com/primitives/docs/components/dialog)

The implementation uses a locked FastMCP 3.4.7 client/server pair, upgraded and regression-tested during the September 2026 security review. The schema, authorization, evidence handling, policy, and investigation workflow are LeakLens application code layered on these libraries.

- [FastMCP 2-to-3 migration guide](https://gofastmcp.com/getting-started/upgrading/from-fastmcp-2)
- [FastMCP security advisories](https://github.com/PrefectHQ/fastmcp/security/advisories)
- [DiskCache pickle advisory](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v) — the dependency was removed by the FastMCP upgrade.

- [Nginx dynamic upstream DNS resolution](https://nginx.org/en/docs/http/ngx_http_upstream_module.html#server): supported by the pinned Nginx 1.28 image; used to follow recreated API containers.
