"""Local ingestion boundary only; deliberately no governed query endpoints."""
from fastapi import FastAPI, HTTPException

from services.application import Application, UnapprovedMapping
from services.mapping import Family
from services.ontology import StrictModel


class IngestionRequest(StrictModel):
    family: Family
    mapping_version: str


def create_app(application: Application) -> FastAPI:
    app = FastAPI(title="Stillroom Lab ingestion")

    @app.post("/ingestions")
    def ingest(request: IngestionRequest) -> dict[str, int]:
        try:
            return {"ingested": application.ingest(request.family, request.mapping_version)}
        except UnapprovedMapping as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    return app
