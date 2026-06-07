import uvicorn

from airway.settings import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "airway.app:create_app",
        factory=True,
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
