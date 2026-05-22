import os
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from database import get_connection, init_db
from models import (
    StudentCreate,
    StudentResponse,
    StudentUpdate,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Student Management API",
    description=(
        "A REST API for managing student records with full CRUD operations.\n\n"
        "**Authentication:** Register at `/api/auth/register`, then log in at "
        "`/api/auth/login` to receive a JWT bearer token. Pass it as "
        "`Authorization: Bearer <token>` on all `/api/students/*` requests."
    ),
    version="2.0.0",
    lifespan=lifespan,
    root_path=os.environ.get("BASE_PATH", ""),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/api/healthz", tags=["Health"])
def health_check():
    return {"status": "ok"}


# ─── Auth ─────────────────────────────────────────────────────────────────────

@app.post("/api/auth/register", response_model=UserResponse, status_code=201, tags=["Auth"])
def register(user: UserCreate):
    """Create a new user account."""
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (user.username,)
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username is already taken.",
            )
        password_hash = hash_password(user.password)
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (user.username, password_hash),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, username, created_at FROM users WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(credentials: UserLogin):
    """Authenticate and receive a JWT access token."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT username, password_hash FROM users WHERE username = ?",
            (credentials.username,),
        ).fetchone()
        if row is None or not verify_password(credentials.password, row["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = create_access_token(subject=row["username"])
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    finally:
        conn.close()


@app.get("/api/auth/me", response_model=UserResponse, tags=["Auth"])
def get_me(current_user: str = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, created_at FROM users WHERE username = ?", (current_user,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


# ─── Students ─────────────────────────────────────────────────────────────────

@app.get("/api/students/stats/summary", tags=["Students"])
def get_stats(_: str = Depends(get_current_user)):
    """Get summary statistics about all students. Requires authentication."""
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        avg_age = conn.execute("SELECT AVG(age) FROM students").fetchone()[0]
        grades = conn.execute(
            "SELECT grade, COUNT(*) as count FROM students GROUP BY grade ORDER BY grade"
        ).fetchall()
        return {
            "total_students": total,
            "average_age": round(avg_age, 1) if avg_age else None,
            "students_by_grade": [dict(r) for r in grades],
        }
    finally:
        conn.close()


@app.post("/api/students", response_model=StudentResponse, status_code=201, tags=["Students"])
def create_student(student: StudentCreate, _: str = Depends(get_current_user)):
    """Create a new student record. Requires authentication."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO students (name, email, age, grade) VALUES (?, ?, ?, ?)",
            (student.name, student.email, student.age, student.grade),
        )
        conn.commit()
        row = cursor.execute(
            "SELECT * FROM students WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(row)
    except Exception as e:
        conn.rollback()
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=409, detail="A student with this email already exists.")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/students", response_model=List[StudentResponse], tags=["Students"])
def list_students(
    search: Optional[str] = Query(None, description="Search by name or email"),
    grade: Optional[str] = Query(None, description="Filter by grade"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    _: str = Depends(get_current_user),
):
    """List all students with optional search, grade filter, and pagination. Requires authentication."""
    conn = get_connection()
    try:
        query = "SELECT * FROM students WHERE 1=1"
        params: list = []

        if search:
            query += " AND (name LIKE ? OR email LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        if grade:
            query += " AND grade = ?"
            params.append(grade)

        query += " ORDER BY id LIMIT ? OFFSET ?"
        params.extend([limit, skip])

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/students/{student_id}", response_model=StudentResponse, tags=["Students"])
def get_student(student_id: int, _: str = Depends(get_current_user)):
    """Retrieve a single student by ID. Requires authentication."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Student with id {student_id} not found.")
        return dict(row)
    finally:
        conn.close()


@app.put("/api/students/{student_id}", response_model=StudentResponse, tags=["Students"])
def update_student(student_id: int, student: StudentUpdate, _: str = Depends(get_current_user)):
    """Partially or fully update a student record. Requires authentication."""
    conn = get_connection()
    try:
        existing = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Student with id {student_id} not found.")

        updates = student.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields provided for update.")

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [student_id]

        conn.execute(f"UPDATE students SET {set_clause} WHERE id = ?", values)
        conn.commit()

        row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=409, detail="A student with this email already exists.")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.delete("/api/students/{student_id}", status_code=204, tags=["Students"])
def delete_student(student_id: int, _: str = Depends(get_current_user)):
    """Delete a student record. Requires authentication."""
    conn = get_connection()
    try:
        existing = conn.execute("SELECT id FROM students WHERE id = ?", (student_id,)).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Student with id {student_id} not found.")
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.commit()
    finally:
        conn.close()
