"""Run the backend in the foreground with application and access logs."""
import logging
import socket

import uvicorn

from app.config import settings


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Never terminate an existing service just because the shortcut was clicked twice.
    with socket.socket() as probe:
        if probe.connect_ex((settings.host, settings.port)) == 0:
            raise SystemExit(
                f"Port {settings.port} is already in use. Close the previous backend "
                "console before starting another instance."
            )
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
        access_log=True,
        ws_max_size=65536,
    )


if __name__ == "__main__":
    main()
