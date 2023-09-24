import os
import asyncio
from httpx import AsyncClient, HTTPError
from sqlalchemy import update
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine.row import Row
from uuid import uuid4

from . import (
    Any,
    Awaitable,
    datetime,
    Dict,
    List,
    logger,
    Set,
    Union,
    HTTPException,
)
from .models import App, AllMonitoredApps, MonitoredApp, MonitoredAppMeta, Queue

# Constants
DATABASE_URI = os.getenv("DATABASE_URI", None)
STRIIM_API_URL = os.getenv("STRIIM_API_URL", None)
SESSION_ID = os.getenv("SESSION_ID", uuid4())

async_engine = create_async_engine(DATABASE_URI, echo=True)
AsyncSessionLocal = sessionmaker(
    bind=async_engine, expire_on_commit=False, class_=AsyncSession
)


class AppInterface:
    def __init__(
        self,
        session: Session = AsyncSessionLocal(),
        http_client: AsyncClient = AsyncClient(),
    ):
        self.session: Session = session
        self.http_client: AsyncClient = http_client
        self.monitoring_apps: Set[str] = set()
        self.monitor_lock = asyncio.Lock()

    @staticmethod
    def __parse_app_row(rows: Union[List[Row], Row]) -> MonitoredAppMeta:
        if isinstance(rows, Row):
            _ = rows[0]
        else:
            raise ValueError("Invalid input, expected Row or List[Row]")
        return MonitoredAppMeta(
            app=_.app,
            status=_.status,
            payload=_.payload,
            created_at=_.created_at,
            updated_at=_.updated_at,
            last_activity_at=_.last_activity_at,
        )

    async def __check_app_exists(self, app_name: str) -> int:
        async with self.session.begin():
            app_count = await self.session.execute(
                select(App.app).where(App.app == app_name)
            )
            return app_count.scalar() or 0

    async def __check_queue_exists(self, app_name: str) -> int:
        async with self.session.begin():
            queue_count = await self.session.execute(
                select(Queue.app).where(Queue.app == app_name)
            )
            return queue_count.scalar() or 0

    async def create_new_monitored_app(self, app: MonitoredApp) -> MonitoredApp:
        app_exists_result = await self.__check_app_exists(app.app)
        queue_exists_result = await self.__check_queue_exists(app.app)

        if app_exists_result == 0 and queue_exists_result == 0:
            new_status = App(
                app=app.app,
                status=app.status,
                payload=app.payload,
                created_at=datetime.utcnow(),
            )

            self.session.add(new_status)
            await self.session.commit()

            return MonitoredApp(
                app=new_status.app,
                status=new_status.status,
                payload=new_status.payload,
            )
        else:
            raise HTTPException(status_code=404, detail="Failed to create new app")

    async def get_monitored_app(self, app_name: str) -> MonitoredAppMeta:
        async with self.session.begin():
            app_status = await self.session.execute(
                select(App).where(App.app == app_name)
            )
            row = app_status.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="App not found")

            return self.__parse_app_row(row)

    async def get_all_monitored_apps(self) -> AllMonitoredApps:
        async with self.session.begin():
            apps_status = await self.session.execute(select(App))
            results = apps_status.fetchall()

            if not results:
                return []
            else:
                return AllMonitoredApps(
                    apps=[self.__parse_app_row(row) for row in results]
                )

    async def monitor_app_status(
        self,
        app_name: str,
    ) -> None:
        try:
            # Fetch the original status from the database
            original_status = await self.get_status(app_name, self.session)
            # Fetch the current status from the external API
            fetched_status = await self.fetch_app_status(app_name, self.http_client)
            if original_status is None or original_status != fetched_status:
                # Update the status in the database
                await self.update_status(app_name, fetched_status, self.session)
                await asyncio.sleep(2)  # ... slow down speed demon
            # Check if payload contains nodowntime_uri and downtime_uri
            if (
                original_status == "COMPLETED"
                and "nodowntime_uri" in fetched_status.get("payload", {})
                and "downtime_uri" in fetched_status.get("payload", {})
            ):
                # Call the start_cdc function with nodowntime_fqn
                nodowntime_fqn = fetched_status.get("payload", {}).get("nodowntime_fqn")
                await self.start_cdc(nodowntime_fqn)
        except Exception as e:
            logger.error(f"Error monitoring app '{app_name}': {str(e)}")

    async def get_status(self, app_name: str) -> str:
        # Query the original status from the database
        app_status = await self.session.execute(select(App).where(App.app == app_name))
        row = app_status.fetchone()
        return row.status if row else None

    async def update_status(
        self, app_name: str, new_status: str, session: Session
    ) -> None:
        # Update the status in the database
        await session.execute(
            update(App).where(App.app == app_name).values(status=new_status)
        )
        await session.commit()

    async def start_monitoring_tasks(self):
        while True:
            tasks: List[Awaitable[None]] = []
            logger.info(f"{SESSION_ID} - I'm up, starting monitoring rounds!")

            async with AsyncSessionLocal() as async_session:
                query = select(App.app)
                apps_to_monitor = await async_session.execute(query)
                apps = [row[0] for row in apps_to_monitor]

                if apps:
                    logger.info(f"{SESSION_ID} - ({len(apps)}) app(s) in-flight")
                    for app_name in apps:
                        async with self.monitor_lock:
                            if app_name not in self.monitoring_apps:
                                task = asyncio.create_task(
                                    self.monitor_app_status(app_name)
                                )
                                tasks.append(task)
                                self.monitoring_apps.add(app_name)
                    logger.info(f"{SESSION_ID} - ({len(tasks)}) tasks(s) queued")
                else:
                    logger.debug(f"{SESSION_ID} - No apps detected to monitor")

            await asyncio.gather(*tasks)
            # Sleep for one minute before recycling
            logger.info(
                f"{SESSION_ID} - Recycling monitoring task and taking a power nap!"
            )
            await asyncio.sleep(60)

    async def fetch_app_status(self, app_name: str) -> Dict[str, Any]:
        logger.info(f"[external-striim] Fetching app status for {app_name}")
        try:
            if not STRIIM_API_URL:
                return None
            else:
                # TOOOO do this
                pass
        except HTTPError:
            raise

    async def start_cdc(self, nodowntime_fqn: str) -> None:
        """wrapper call to start cdc app"""
        logger.info(f"[external-striim] Starting CDC app {nodowntime_fqn}")
        try:
            if not STRIIM_API_URL:
                return None
            else:
                # TOOOO do this
                pass
        except HTTPError:
            raise
