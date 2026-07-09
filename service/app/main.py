"""Ingestion workflow app backend. See docs/app-spec.md.

Run with: uvicorn app.main:app --reload --app-dir service
"""
from fastapi import FastAPI

from .routers import drafts, inbox, recipes, schema_routes

app = FastAPI(
    title="Stirfry Companion — Ingestion API",
    description=(
        "Backend for the recipe ingestion workflow app: browse inbox "
        "captures, review/edit drafts, promote to the trusted collection. "
        "Normalization stays manual/interactive by design (see "
        "docs/app-spec.md Non-goals) — this API never calls an LLM itself."
    ),
)

app.include_router(inbox.router)
app.include_router(drafts.router)
app.include_router(recipes.router)
app.include_router(schema_routes.router)


@app.get("/health")
def health():
    return {"status": "ok"}
