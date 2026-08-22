"""``GET /health`` — the companion's unauthenticated identity probe (FR-14, AD-4)."""

from fastapi import APIRouter, Request

from src.companion.app.state import connection_registry
from src.companion.contracts import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def read_health(request: Request) -> HealthResponse:
    """Report that this process is alive and say which process it is.

    Deliberately requires **no authentication**: it is what a caller reads *before* deciding to
    send its token, to confirm that whatever holds the discovered port is this companion and not an
    unrelated local server (AD-4). There is no failure path to model — a companion that cannot
    answer does not answer at all — so under a running lifespan the response is always ``200`` with
    ``status="ok"``. The lifespan is a real precondition: served without one (no supported path
    does), the missing ``instance_id`` is an unhandled error, not a modelled state.

    ``clients`` is the connection registry's live count (17.4) — how many tabs hold a WebSocket at
    this instant, read through ``connection_registry`` in ``src.companion.app.state`` like every
    other reader of that state. ``None`` when the registry does not exist — a constructed but
    never-started app, which no supported serving path produces but a test can — and the optional
    wire shape also lets an older leaf read a newer companion's body and vice versa.

    Args:
        request: The incoming request, used only to reach ``app.state.instance_id``, which the
            lifespan minted at startup, and the connection registry beside it.

    Returns:
        The health resource itself, unwrapped: AD-16 keeps the MCP result envelope out of REST.
    """
    registry = connection_registry(request.app)
    return HealthResponse(
        status="ok",
        instance_id=request.app.state.instance_id,
        clients=None if registry is None else registry.connected_count,
    )
