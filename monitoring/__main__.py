from .api import MonitoringService


def main(host, port) -> None:
    MonitoringService(host, port).run()


def cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Monitoring API")
    parser.add_argument("command", choices=["run"], help="Command to execute")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host for FastAPI service",
        required=False,
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for FastAPI service",
        required=False,
    )
    args = parser.parse_args()

    if args.command == "run":
        main(host=args.host, port=args.port)
    else:
        print("Invalid command - Use 'run'")
