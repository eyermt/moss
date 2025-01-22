"""
Copyright 2025 the MOSS project.
Point person for this file: Sam Schwartz (samuel.d.schwartz@gmail.com)
Description:
This is the main.py file, which should be run to start the app.
This can be done by running the following command:

python3 main.py
"""

import uvicorn
from fastapi import FastAPI
from hex.biz_logic import router as biz_router


def _ini_api_app() -> FastAPI:
    """Helper/factory function for initializing and returning a FastAPI instance.

    Returns:
        FastAPI: a fresh FastAPI instance
    """
    app = FastAPI()
    return app


def _ini_hex_administration(app: FastAPI) -> FastAPI:
    """Helper function for initiating anything to do with CLI administration.

    Args:
        app (FastAPI): The FastAPI app

    Returns:
        FastAPI: The app, possibly changed with CLI-related modifications.
    """
    return app


def _ini_hex_biz(app: FastAPI) -> FastAPI:
    """Helper function for initiating anything to do with buisness logic.
    Specifically, adding RESTful endpoints, routers, and versioning

    Args:
        app (FastAPI): The application

    Returns:
        FastAPI: The app, now with base routes added.
    """
    app.include_router(
        biz_router,
        prefix="/v1",
        tags=["v1"],
        responses={404: {"description": "Not found"}},
    )

    @app.get("/")
    def read_root():
        return {"Hello": "World"}

    return app


def _ini_hex_notification(app: FastAPI) -> FastAPI:
    """Helper function for setting up any notifications to the application.

    Args:
        app (FastAPI): The application

    Returns:
        FastAPI: The app, possibly changed with notification-related modifications.
    """
    return app


def _ini_hex_persistance(app):
    """Helper function for setting up database connections for the application.

    Args:
        app (FastAPI): The application

    Returns:
        FastAPI: The app, possibly changed with database-related modifications.
    """
    return app



def main() -> FastAPI:
    """Initializes the app when called from the command line.

    Returns:
        FastAPI: The FastAPI app for the api server to serve.
    """
    app = _ini_api_app()
    _ini_hex_persistance(app)
    _ini_hex_notification(app)
    _ini_hex_administration(app)
    _ini_hex_biz(app)
    return app


if __name__ == "__main__":
    app = main()
    uvicorn.run(app, host="0.0.0.0", port=8000)