from fastapi import FastAPI
import os
import time
from pydantic import BaseModel
from typing import Literal
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse



import sqlite3
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production
    allow_methods=["*"],
    allow_headers=["*"],
)




DB_PATH = os.environ.get("DB_PATH", "pomodoro.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task TEXT NOT NULL,
        duration INTEGER NOT NULL,
        mode TEXT NOT NULL,
        status TEXT NOT NULL,
        timer INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )

    """)

conn.commit()

class SessionCreate(BaseModel):
    method : Literal["Work","Short Break","Long Break"]
    timer : int = 0
    # format : bool
    task : str
    # status : Literal["Running","Restarted","Paused","Cancelled","Completed"]

class SessionUpdate(BaseModel):
    status: Literal["Running","Restarted", "Paused", "Cancelled", "Completed"]
    timer: int

# fetch html
@app.get("/")
async def frontend():
    return FileResponse("index.html")

#fetch image
@app.get("/favicon.png")
async def favicon():
    return FileResponse("favicon.png")


# set pomodoro
@app.post("/set_timer")
async def set_timer(data : SessionCreate):
    duration = data.timer
    task = data.task
    mode = data.method
    status = "Running"
    cursor.execute(
        "INSERT INTO sessions (timer, task, duration, mode,status) VALUES (?, ?, ?, ?, ?)",
        (data.timer,task, duration, mode, status)
    )
    conn.commit()


    return {"id" : cursor.lastrowid, "duration":duration , "task": task,"mode":mode}


# update backend 
@app.put("/update_timer/{session_id}")
async def update_timer(session_id :int, data : SessionUpdate):

    cursor.execute(
        "UPDATE sessions SET status = ?, timer = ?,updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (data.status, data.timer, session_id)
    )
    conn.commit()
    
    return {"id": session_id, "status": data.status, "timer": data.timer}


@app.put("/task_complete/{session_id}")
async def task_complete(session_id : int):
    cursor.execute(
        "UPDATE sessions SET status = ?, timer = ?,updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        ("completed", 0, session_id)
    )
    conn.commit()

    return {"id": session_id, "status": "Completed"}


# get request for report analysis
@app.get("/fetch_active_timer")
async def fetch_active_timer():
    cursor.execute(
        "SELECT * FROM sessions WHERE status IN (?, ?)",
        ("Running", "Paused")
    )
    rows = cursor.fetchall()
    
    return [
        {
            "id": r[0],
            "task": r[1],
            "duration": r[2],
            "mode": r[3],
            "status": r[4],
            "timer": r[5],
            "created_at": r[6],
            "updated_at": r[7],
        }
        for r in rows
    ]


class TimerBeat(BaseModel):
    timer: int


@app.put("/heartbeat/{session_id}")
async def heartbeat(session_id: int, data: TimerBeat):
    cursor.execute(
        "UPDATE sessions SET timer = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (data.timer, session_id),
    )
    conn.commit()
    return {"id": session_id, "timer": data.timer}

