"""Local operator ingestion and separately governed read-only queries."""
from typing import assert_never
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from starlette.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from services.query import OutcomeCode, QueryRequest, QueryService
from services.query_storage import provision_queries

from services.application import Application, UnapprovedMapping
from services.mapping import Family
from services.ontology import StrictModel


class IngestionRequest(StrictModel):
    family: Family
    mapping_version: str


def status_code(code: OutcomeCode) -> int:
    """Adding an outcome requires an explicit HTTP status before typechecking passes."""
    match code:
        case 'query_not_allowlisted' | 'invalid_parameters' | 'invalid_request':
            return 422
        case 'permission_denied':
            return 403
        case 'incomplete_evidence':
            return 200
        case 'query_failed':
            return 503
    assert_never(code)


def create_app(application: Application) -> FastAPI:
    app = FastAPI(title="Stillroom Lab")
    provision_queries(application.store)
    queries = QueryService(application.store.schema)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        if request.url.path != '/queries':
            return await request_validation_exception_handler(request, exc)
        result = await run_in_threadpool(queries.reject_invalid, exc.body)
        return JSONResponse(status_code=422, content=result.model_dump(mode='json'))

    @app.post('/queries')
    def query(request: QueryRequest) -> JSONResponse:
        result = queries.execute(request)
        return JSONResponse(status_code=status_code(result.reason.code),
                           content=result.model_dump(mode='json'))

    @app.post("/ingestions")
    def ingest(request: IngestionRequest) -> dict[str, int]:
        try:
            return {"ingested": application.ingest(request.family, request.mapping_version)}
        except UnapprovedMapping as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    return app
