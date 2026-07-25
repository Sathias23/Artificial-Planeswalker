"""The companion's wire contract — pydantic models shared by the app and the leaf (AD-3, AD-12).

These models are the **single source of truth** for every shape that crosses the companion's HTTP
and WebSocket boundary: the backend declares them as ``response_model`` so they land in
``app.openapi()``, and the TypeScript the frontend compiles against is generated from that same
schema (AD-12). A hand-built ``dict`` return would leave the generator with nothing to emit, so a
second shape would drift into existence — exactly what AD-1 and AD-12 exist to prevent.

This module is a **leaf** (AD-3): it may import only the stdlib, ``pydantic``, ``httpx``,
``src.paths`` and its sibling leaf modules — never ``fastapi``, ``sqlalchemy`` or
``src.companion.app``, and not even under ``if TYPE_CHECKING:``. That constraint is what lets the
MCP server import these models (the AD-4 identity probe lives in the leaf and is shared by the
startup check and the companion tools) without a stdio session transitively importing a web
framework. ``tests/unit/companion/test_import_boundary.py`` enforces it.
"""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """The body of ``GET /health`` — the companion's unauthenticated identity probe (FR-14).

    A caller reads this *before* deciding to send its token: it confirms that whatever answered on
    the discovered port is this companion process and not some unrelated local server that happens
    to hold the port (AD-4). ``status`` is deliberately **not** the project's MCP result envelope
    (AD-16 bans that from REST) — the body *is* the health resource and ``status`` is a field of it.

    Attributes:
        status: A closed token, extendable only by adding a member to the ``Literal``. Always
            ``"ok"`` today; ``/health`` has no failure path to model, since a companion that cannot
            answer does not answer at all.
        instance_id: The per-process identity minted at startup, echoed so a caller can match it
            against the value the discovery file advertised.

    Example:
        >>> HealthResponse(status="ok", instance_id="0f6e...").status
        'ok'
    """

    status: Literal["ok"]
    instance_id: str
