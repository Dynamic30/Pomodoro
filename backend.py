from fastapi import FastAPI
import os
# import time
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
        user_id INTEGER NOT NULL,
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

cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        password TEXT,
        theme TEXT DEFAULT 'light',
        sound_duration INTEGER DEFAULT 10
    )
""")

# Default users
cursor.execute("INSERT OR IGNORE INTO users (name, password, theme) VALUES (?, ?, ?)", ("admin", "admin", "light"))
cursor.execute("INSERT OR IGNORE INTO users (name, password, theme) VALUES (?, ?, ?)", ("temp", None, "light"))
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


# Basic User configurations

class UserCreate(BaseModel):
    name: str
    password: str = None  # optional

class UserLogin(BaseModel):
    password: str

class UserSettings(BaseModel):
    password: str = None
    theme: Literal["light", "dark", "sepia"] = None
    sound_duration: int = None

@app.get("/users")
async def get_users():
    cursor.execute("SELECT id, name, password IS NOT NULL as has_password, theme, sound_duration FROM users ORDER BY id")
    return [
        {"id": r[0], "name": r[1], "has_password": bool(r[2]), "theme": r[3], "sound_duration":r[4] or 10}
        for r in cursor.fetchall()
    ]

@app.post("/users")
async def create_user(data : UserCreate):
    cursor.execute(
         "INSERT INTO users (name, password) VALUES (?, ?)",
        (data.name, data.password)
    )
    conn.commit()
    return {"id": cursor.lastrowid, "name": data.name, "has_password": data.password is not None}

@app.post("/users/{user_id}/login")
async def login(user_id: int, data: UserLogin):
    cursor.execute("SELECT password FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        return {"success": False, "error": "User not found"}
    if row[0] is None:
        return {"success": True}  # no password set
    if row[0] != data.password:
        return {"success": False, "error": "Wrong password"}
    return {"success": True}

@app.put("/users/{user_id}/settings")
async def update_settings(user_id: int, data: UserSettings):
    if data.theme:
        cursor.execute("UPDATE users SET theme = ? WHERE id = ?", (data.theme, user_id))
    if data.password is not None:
        pwd = data.password if data.password != "" else None
        cursor.execute("UPDATE users SET password = ? WHERE id = ?", (pwd, user_id))
    if data.sound_duration is not None:
        clamped = max(5, min(20, data.sound_duration))
        cursor.execute("UPDATE users SET sound_duration = ? WHERE id = ?", (clamped, user_id))

    conn.commit()
    return {"updated": True}


#fetch image
@app.get("/favicon.png")
async def favicon():
    return FileResponse("favicon.png")


# set pomodoro
@app.post("/{user_id}/set_timer")
async def set_timer(user_id: int,data : SessionCreate):
    duration = data.timer
    task = data.task
    mode = data.method
    status = "Running"
    cursor.execute(
        "INSERT INTO sessions (user_id, timer, task, duration, mode,status) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, data.timer,task, duration, mode, status)
    )
    conn.commit()


    return {"id" : cursor.lastrowid, "duration":duration , "task": task,"mode":mode}


# update backend 
@app.put("/{user_id}/update_timer/{session_id}")
async def update_timer(user_id :int,session_id :int, data : SessionUpdate):

    cursor.execute(
        "UPDATE sessions SET status = ?, timer = ?,updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
        (data.status, data.timer, session_id, user_id)
    )
    conn.commit()
    
    return {"id": session_id, "status": data.status, "timer": data.timer}


@app.put("/{user_id}/task_complete/{session_id}")
async def task_complete(user_id :int ,session_id : int):
    cursor.execute(
        "UPDATE sessions SET status = ?, timer = ?,updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
        ("Completed", 0, session_id, user_id)
    )
    conn.commit()

    return {"id": session_id, "status": "Completed"}


# get request for report analysis
@app.get("/{user_id}/fetch_active_timer")
async def fetch_active_timer(user_id:int):
    cursor.execute(
        "SELECT * FROM sessions WHERE user_id = ? AND status IN (?, ?)",
        (user_id, "Running", "Paused")
    )
    rows = cursor.fetchall()
    
    return [
        {
            "id": r[0],
            "user_id": r[1],
            "task": r[2],
            "duration": r[3],
            "mode": r[4],
            "status": r[5],
            "timer": r[6],
            "created_at": r[7],
            "updated_at": r[8],
        }
        for r in rows
    ]


class TimerBeat(BaseModel):
    timer: int


@app.put("/{user_id}/heartbeat/{session_id}")
async def heartbeat(user_id:int, session_id: int, data: TimerBeat):
    cursor.execute(
        "UPDATE sessions SET timer = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
        (data.timer, session_id, user_id),
    )
    conn.commit()
    return {"id": session_id, "timer": data.timer}

