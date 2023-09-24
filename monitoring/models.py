from typing import Dict, List, Union
from datetime import datetime
from pydantic import BaseModel, validator
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class App(Base):
    """Represents an application"""

    __tablename__ = "apps"
    app = Column(String, primary_key=True)
    status = Column(String)
    payload = Column(JSONB)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_activity_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Queue(Base):
    """Represents a queue"""

    __tablename__ = "_queue"
    app = Column(String, primary_key=True)
    status = Column(String)
    app_uri = Column(String)
    created_at = Column(DateTime, server_default=func.now())


class MonitoredApp(BaseModel):
    """Represents a monitored application"""

    app: str
    status: str
    payload: Union[Dict[str, str], str]

    @validator("status")
    def validate_status(cls, status):
        # these statuses map to the public.app object as constraint lookup
        valid_statuses = {
            "APPROVING QUIESCE",
            "COMPLETED",
            "CREATED",
            "DEPLOY FAILED",
            "DEPLOYED",
            "DEPLOYING",
            "FLUSHING",
            "HALT",
            "NOT ENOUGH SERVERS",
            "QUIESCED",
            "QUIESCING",
            "RECOVERING SOURCES",
            "RUNNING",
            "STARTING",
            "STARTING SOURCES",
            "STOPPED",
            "STOPPING",
            "TERMINATED",
            "UNKNOWN",
            "VERIFYING STARTING",
        }
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}")
        return status


class MonitoredAppMeta(MonitoredApp):
    """Represents a monitored application with metadata"""

    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime


class AllMonitoredApps(BaseModel):
    """Represents a list of monitored applications"""

    apps: List[MonitoredAppMeta]
