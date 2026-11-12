from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import Json, execute_values
from psycopg2.pool import ThreadedConnectionPool
from pydantic import BaseModel

DB_DSN = "dbname=db user=postgresql password=***** host=localhost port=5432"

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
pool = ThreadedConnectionPool(1, 10, DB_DSN)

DDL = """
CREATE TABLE IF NOT EXISTS table_name (
    event_id         TEXT PRIMARY KEY,
    user_id          TEXT,
    session_id       TEXT NOT NULL,
    event_ts         TIMESTAMPTZ NOT NULL,
    received_ts      TIMESTAMPTZ NOT NULL,
    interaction_type TEXT NOT NULL,
    page_name        TEXT NOT NULL,
    button_name      TEXT,
    feature_name     TEXT,
    element_id       TEXT,
    device           TEXT,
    app_version      TEXT
);
ALTER TABLE raw_events ADD COLUMN IF NOT EXISTS properties JSONB;
CREATE INDEX IF NOT EXISTS ix_raw_events_ts      ON raw_events (event_ts);
CREATE INDEX IF NOT EXISTS ix_raw_events_session ON raw_events (session_id);
CREATE INDEX IF NOT EXISTS ix_raw_events_type    ON raw_events (interaction_type);
"""

conn = pool.getconn()
try:
    with conn, conn.cursor() as cur:
        cur.execute(DDL)
finally:
    pool.putconn(conn)


class Event(BaseModel):
    event_id: str
    user_id: Optional[str] = None
    session_id: str
    event_ts: datetime
    interaction_type: str
    page_name: str
    button_name: Optional[str] = None
    feature_name: Optional[str] = None
    element_id: Optional[str] = None
    device: Optional[str] = None
    app_version: Optional[str] = None
    properties: Optional[dict] = None


@app.post("/track")
def track(events: List[Event]):
    now = datetime.now(timezone.utc)
    rows = [
        (e.event_id, e.user_id, e.session_id, e.event_ts, now, e.interaction_type,
         e.page_name, e.button_name, e.feature_name, e.element_id, e.device,
         e.app_version, Json(e.properties) if e.properties is not None else None)
        for e in events
    ]
    conn = pool.getconn()
    try:
        with conn, conn.cursor() as cur:
            execute_values(
                cur,
                """INSERT INTO raw_events
                   (event_id, user_id, session_id, event_ts, received_ts, interaction_type,
                    page_name, button_name, feature_name, element_id, device, app_version, properties)
                   VALUES %s ON CONFLICT (event_id) DO NOTHING""",
                rows,
            )
        return {"accepted": len(rows)}
    finally:
        pool.putconn(conn)