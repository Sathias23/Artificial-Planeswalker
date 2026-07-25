"""``GET /health`` — the companion's unauthenticated identity probe (FR-14, AD-4)."""

from fastapi import APIRouter, Request

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

    Args:
        request: The incoming request, used only to reach ``app.state.instance_id``, which the
            lifespan minted at startup.

    Returns:
        The health resource itself, unwrapped: AD-16 keeps the MCP result envelope out of REST.
    """
    return HealthResponse(status="ok", instance_id=request.app.state.instance_id)
