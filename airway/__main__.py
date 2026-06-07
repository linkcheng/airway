import sys

from airway.adapters.bisheng.auth import BishengAuthProvider
from airway.adapters.bisheng.client import BishengHttpClient
from airway.config import load_config


def main() -> None:
    config = load_config()
    auth = BishengAuthProvider(config)
    client = BishengHttpClient(config, auth)

    import airway.server as srv

    srv._config = config
    srv._client = client

    transport = "stdio"
    kwargs = {}

    if "--transport" in sys.argv:
        idx = sys.argv.index("--transport")
        if idx + 1 < len(sys.argv):
            transport = sys.argv[idx + 1]

    if transport in ("http", "streamable-http"):
        kwargs = {"transport": "streamable-http", "host": config.server.host, "port": config.server.port}

    srv.mcp.run(**kwargs)


if __name__ == "__main__":
    main()
