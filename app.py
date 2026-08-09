from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent
DB = BASE / "civicflow.db"

app = FastAPI(title="CivicFlow API", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

CATEGORIES = {"Roads", "Streetlights", "Waste", "Water", "Public Safety", "Other"}
STATUSES = {"Reported", "In Review", "Assigned", "In Progress", "Resolved"}
PRIORITIES = {"Low", "Medium", "High", "Critical"}

class IssueCreate(BaseModel):
    title: str = Field(min_length=4, max_length=120)
    description: str = Field(min_length=10, max_length=1000)
    category: str
    location: str = Field(min_length=2, max_length=180)
    reporter: str = Field(default="Anonymous", min_length=2, max_length=80)

class IssueUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
    update_note: Optional[str] = Field(default=None, max_length=500)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        location TEXT NOT NULL,
        reporter TEXT NOT NULL,
        priority TEXT NOT NULL,
        status TEXT NOT NULL,
        assignee TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        issue_id INTEGER NOT NULL,
        note TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(issue_id) REFERENCES issues(id) ON DELETE CASCADE
    );
    """)
    count = c.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
    if count == 0:
        seed = [
            ("Deep pothole near bus stop", "Large pothole is forcing two-wheelers into traffic near the main bus stop.", "Roads", "Station Road, Ward 12", "Riya Sen", "High", "In Progress", "Roads Team"),
            ("Streetlight not working", "The light has been off for three nights and the lane becomes very dark after 8 PM.", "Streetlights", "Lake View Lane, Ward 4", "Arjun Das", "Medium", "Assigned", "Electrical Team"),
            ("Overflowing community bin", "The public bin is overflowing and waste is spreading onto the footpath.", "Waste", "Market Square, Ward 7", "Anonymous", "High", "Reported", None),
            ("Leaking water main", "Clean water has been leaking continuously from a roadside pipe since yesterday.", "Water", "MG Road, Ward 2", "Maya Roy", "Critical", "Resolved", "Water Team"),
            ("Damaged park railing", "A section of the children's park railing is loose and needs repair.", "Public Safety", "Central Park, Ward 9", "Kabir Paul", "Medium", "In Review", "Safety Team"),
        ]
        ts = now()
        c.executemany("""INSERT INTO issues(title,description,category,location,reporter,priority,status,assignee,created_at,updated_at)
                         VALUES(?,?,?,?,?,?,?,?,?,?)""", [r + (ts, ts) for r in seed])
        issue_id = c.execute("SELECT id FROM issues WHERE title=?", (seed[0][0],)).fetchone()[0]
        c.execute("INSERT INTO updates(issue_id,note,created_at) VALUES(?,?,?)", (issue_id, "Roads team has scheduled a patch crew for this week.", ts))
    c.commit(); c.close()

init_db()

@app.get("/")
def home():
    return FileResponse(BASE / "templates" / "index.html")


def priority_for(category: str, description: str) -> str:
    text = f"{category} {description}".lower()
    if any(x in text for x in ["danger", "accident", "unsafe", "electric shock", "sewage", "water main"]):
        return "Critical"
    if category in {"Roads", "Water", "Public Safety"}:
        return "High"
    if category in {"Streetlights", "Waste"}:
        return "Medium"
    return "Low"


def issue_payload(row):
    c = conn()
    updates = [dict(x) for x in c.execute("SELECT id,note,created_at FROM updates WHERE issue_id=? ORDER BY id DESC", (row["id"],)).fetchall()]
    c.close()
    item = dict(row)
    item["updates"] = updates
    return item

@app.get("/api/issues")
def list_issues(status: Optional[str] = None, category: Optional[str] = None, q: Optional[str] = None, limit: int = Query(50, ge=1, le=100)):
    c = conn()
    clauses, args = [], []
    if status and status != "All": clauses.append("status=?"); args.append(status)
    if category and category != "All": clauses.append("category=?"); args.append(category)
    if q:
        clauses.append("(title LIKE ? OR description LIKE ? OR location LIKE ?)")
        term = f"%{q}%"; args += [term, term, term]
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = c.execute(f"SELECT * FROM issues{where} ORDER BY CASE priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, id DESC LIMIT ?", args + [limit]).fetchall()
    c.close()
    return [issue_payload(r) for r in rows]

@app.get("/api/issues/{issue_id}")
def get_issue(issue_id: int):
    c = conn(); row = c.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone(); c.close()
    if not row: raise HTTPException(404, "Issue not found")
    return issue_payload(row)

@app.post("/api/issues", status_code=201)
def create_issue(payload: IssueCreate):
    if payload.category not in CATEGORIES: raise HTTPException(400, "Invalid category")
    priority = priority_for(payload.category, payload.description)
    ts = now(); c = conn()
    cur = c.execute("""INSERT INTO issues(title,description,category,location,reporter,priority,status,assignee,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""", (payload.title.strip(), payload.description.strip(), payload.category, payload.location.strip(), payload.reporter.strip(), priority, "Reported", None, ts, ts))
    issue_id = cur.lastrowid
    c.execute("INSERT INTO updates(issue_id,note,created_at) VALUES(?,?,?)", (issue_id, "Report received. CivicFlow created a tracking ticket.", ts))
    c.commit(); row = c.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone(); c.close()
    return issue_payload(row)

@app.patch("/api/issues/{issue_id}")
def update_issue(issue_id: int, payload: IssueUpdate):
    if payload.status and payload.status not in STATUSES: raise HTTPException(400, "Invalid status")
    if payload.priority and payload.priority not in PRIORITIES: raise HTTPException(400, "Invalid priority")
    c = conn(); row = c.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone()
    if not row: c.close(); raise HTTPException(404, "Issue not found")
    fields, args = [], []
    for name in ["status", "priority", "assignee"]:
        value = getattr(payload, name)
        if value is not None:
            fields.append(f"{name}=?"); args.append(value.strip() if isinstance(value, str) else value)
    ts = now(); fields.append("updated_at=?"); args.append(ts); args.append(issue_id)
    c.execute(f"UPDATE issues SET {', '.join(fields)} WHERE id=?", args)
    if payload.update_note and payload.update_note.strip():
        c.execute("INSERT INTO updates(issue_id,note,created_at) VALUES(?,?,?)", (issue_id, payload.update_note.strip(), ts))
    c.commit(); row = c.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone(); c.close()
    return issue_payload(row)

@app.get("/api/stats")
def stats():
    c = conn()
    total = c.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
    resolved = c.execute("SELECT COUNT(*) FROM issues WHERE status='Resolved'").fetchone()[0]
    active = total - resolved
    critical = c.execute("SELECT COUNT(*) FROM issues WHERE priority='Critical' AND status!='Resolved'").fetchone()[0]
    categories = [dict(r) for r in c.execute("SELECT category, COUNT(*) count FROM issues GROUP BY category ORDER BY count DESC").fetchall()]
    statuses = [dict(r) for r in c.execute("SELECT status, COUNT(*) count FROM issues GROUP BY status").fetchall()]
    c.close()
    return {"total": total, "active": active, "resolved": resolved, "critical": critical, "resolution_rate": round((resolved / total * 100) if total else 0), "categories": categories, "statuses": statuses}
