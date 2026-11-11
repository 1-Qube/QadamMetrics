"""Document loading kept outside the route module to avoid an import cycle."""

from app.analytics.textbook_intelligence.engine import load_document


def ingest_upload(payload: bytes, filename: str) -> str:
    return load_document(payload, filename)
