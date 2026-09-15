"""API de La Elotiza."""

import argparse

import uvicorn


def main() -> None:
    """Inicia el servidor de la API."""
    parser = argparse.ArgumentParser(description="API de La Elotiza")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run(
        "la_elotiza_api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
