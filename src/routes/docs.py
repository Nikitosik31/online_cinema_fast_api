"""Protected API documentation pages (Swagger UI, ReDoc and the OpenAPI schema)."""

from fastapi import APIRouter, Depends, Request
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from starlette.responses import HTMLResponse

from security.dependencies import get_docs_user

router = APIRouter(dependencies=[Depends(get_docs_user)])


@router.get("/openapi.json", include_in_schema=False)
async def openapi_schema(request: Request) -> dict:
    """
    Return the OpenAPI schema of the application as JSON.

    Replaces the built-in `/openapi.json`, which is disabled in `main.py`.
    Both documentation pages load the schema from here, so protecting it
    hides the full list of endpoints from unauthorized users.

    Args:
        request (Request): The current request, used to reach the application.

    Returns:
        dict: The OpenAPI schema.

    Raises:
        HTTPException: 401 or 403, raised by `get_docs_user`.
    """

    return request.app.openapi()


@router.get("/docs", include_in_schema=False)
async def swagger_ui(request: Request) -> HTMLResponse:
    """
    Return the Swagger UI page.

    Replaces the built-in `/docs`, which is disabled in `main.py`. Only
    moderators and administrators can open it (HTTP Basic authentication).

    Args:
        request (Request): The current request, used to read the application title.

    Returns:
        HTMLResponse: The Swagger UI page, configured to load the schema
            from the protected `/openapi.json`.

    Raises:
        HTTPException: 401 or 403, raised by `get_docs_user`.
    """

    return get_swagger_ui_html(
        openapi_url="/openapi.json", title=request.app.title
    )


@router.get("/redoc", include_in_schema=False)
async def redoc_ui(request: Request) -> HTMLResponse:
    """
    Return the ReDoc page.

    Replaces the built-in `/redoc`, which is disabled in `main.py`. Only
    moderators and administrators can open it (HTTP Basic authentication).

    Args:
        request (Request): The current request, used to read the application title.

    Returns:
        HTMLResponse: The ReDoc page, configured to load the schema from
            the protected `/openapi.json`.

    Raises:
        HTTPException: 401 or 403, raised by `get_docs_user`.
    """

    return get_redoc_html(openapi_url="/openapi.json", title=request.app.title)
