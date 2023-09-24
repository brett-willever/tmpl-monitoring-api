import time
import threading
import asyncio
from fastapi import FastAPI, HTTPException
from uvicorn import run as uvicorn_run

from . import logger
from .models import AllMonitoredApps, MonitoredApp, MonitoredAppMeta
from .tasks import AppInterface

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000


class MonitoringService:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.app = FastAPI(title="Monitoring API")
        self.app_interface = AppInterface()
        self.host = host
        self.port = port
        self.monitoring_thread = None

        self.configure_routes()

    def configure_routes(self):
        @self.app.on_event("startup")
        async def startup_event() -> None:
            try:
                logger.info("Starting the monitoring background task manager.")
                self.start_monitoring_thread()
            except Exception as e:
                logger.error(
                    f"Issues starting the monitoring background task manager: {str(e)}"
                )
                raise RuntimeError(
                    "Issues starting the monitoring background task manager"
                ) from e

        @self.app.post("/monitor/app", response_model=MonitoredApp)
        async def monitor_app(
            app: MonitoredApp,
        ) -> MonitoredApp:
            try:
                result = await self.app_interface.create_new_monitored_app(app)
                return result
            except Exception as e:
                logger.error(f"Failed to create new app: {str(e)}")
                raise HTTPException(status_code=500, detail="Internal Server Error")

        @self.app.get("/app/{app_name}", response_model=MonitoredAppMeta)
        async def get_app(app_name: str) -> MonitoredAppMeta:
            try:
                result = await self.app_interface.get_monitored_app(app_name)
                return result
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to retrieve app: {str(e)}")
                raise HTTPException(status_code=500, detail="Internal Server Error")

        @self.app.get("/app", response_model=AllMonitoredApps)
        async def get_all_apps() -> AllMonitoredApps:
            try:
                result = await self.app_interface.get_all_monitored_apps()
                return result
            except Exception as e:
                logger.error(f"Failed to retrieve all apps: {str(e)}")
                raise HTTPException(status_code=500, detail="Internal Server Error")

    def start_monitoring_thread(self):
        async def monitoring_loop() -> None:
            await self.app_interface.start_monitoring_tasks()

        def _():
            asyncio.set_event_loop(asyncio.new_event_loop())
            loop = asyncio.get_event_loop()
            loop.run_until_complete(monitoring_loop())

        self.monitoring_thread = threading.Thread(target=_)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()

    def run(self):
        time.sleep(2)
        uvicorn_run(
            self.app,
            host=self.host or DEFAULT_HOST,
            port=self.port or DEFAULT_PORT,
            lifespan="on",
        )
