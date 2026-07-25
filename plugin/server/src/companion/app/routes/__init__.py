"""HTTP routers for the companion backend, one module per resource.

Each module exposes a module-level ``router`` (an ``APIRouter``) that
:func:`src.companion.app.main.build_app` includes. Routers are declared with a ``response_model``
drawn from :mod:`src.companion.contracts` so every shape reaches ``app.openapi()`` and, through it,
the generated TypeScript the frontend compiles against (AD-12).
"""
