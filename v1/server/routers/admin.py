from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from datetime import datetime
import sqlite3

from ..deps import require_admin
from ...Database.database_logic import get_db
from ..logging_config import log_event

router = APIRouter()


@router.get("/dashboard")
def get_admin_dashboard(admin=Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    """
    Admin Dashboard - Overview of the entire MobyPark system

    Returns statistics about users, parking lots, sessions, vehicles, and payments.
    """
    log_event("INFO", event="admin_dashboard_accessed",
              message="admin_accessed_dashboard",
              username=admin.get("username"))
    dashboard_data = {}

    # === USER STATISTICS ===
    total_users = con.execute("SELECT COUNT(*) as count FROM users").fetchone()["count"]
    admin_users = con.execute("SELECT COUNT(*) as count FROM users WHERE role = 'ADMIN'").fetchone()["count"]
    regular_users = total_users - admin_users

    # Recent users (last 30 days)
    recent_users = con.execute("""
        SELECT COUNT(*) as count FROM users
        WHERE datetime(created_at) >= datetime('now', '-30 days')
    """).fetchone()["count"]

    dashboard_data["users"] = {
        "total": total_users,
        "admins": admin_users,
        "regular_users": regular_users,
        "recent_new_users": recent_users
    }

    # === PARKING LOT STATISTICS ===
    total_parking_lots = con.execute("SELECT COUNT(*) as count FROM parking_lots").fetchone()["count"]

    # Total capacity and current occupancy
    capacity_data = con.execute("""
        SELECT
            COALESCE(SUM(capacity), 0) as total_capacity,
            COALESCE(SUM(reserved), 0) as total_reserved
        FROM parking_lots
    """).fetchone()

    total_capacity = capacity_data["total_capacity"]
    total_reserved = capacity_data["total_reserved"]

    dashboard_data["parking_lots"] = {
        "total": total_parking_lots,
        "total_capacity": total_capacity,
        "total_reserved": total_reserved,
        "available_spots": total_capacity - total_reserved,
        "occupancy_rate": round((total_reserved / total_capacity * 100) if total_capacity > 0 else 0, 2)
    }

    # === SESSION STATISTICS ===
    total_sessions = con.execute("SELECT COUNT(*) as count FROM sessions").fetchone()["count"]
    active_sessions = con.execute("SELECT COUNT(*) as count FROM sessions WHERE stopped IS NULL").fetchone()["count"]
    completed_sessions = total_sessions - active_sessions

    dashboard_data["sessions"] = {
        "total": total_sessions,
        "active": active_sessions,
        "completed": completed_sessions
    }

    # === VEHICLE STATISTICS ===
    total_vehicles = con.execute("SELECT COUNT(*) as count FROM vehicles").fetchone()["count"]

    dashboard_data["vehicles"] = {
        "total": total_vehicles
    }

    # === PAYMENT STATISTICS ===
    payment_stats = con.execute("""
        SELECT
            COUNT(*) as total_payments,
            COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) as total_revenue,
            COALESCE(SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END), 0) as total_refunds,
            COALESCE(SUM(amount), 0) as net_revenue,
            COALESCE(SUM(CASE WHEN completed = 1 THEN amount ELSE 0 END), 0) as completed_revenue,
            COUNT(CASE WHEN completed = 0 THEN 1 END) as pending_payments
        FROM payments
    """).fetchone()

    dashboard_data["payments"] = {
        "total_payments": payment_stats["total_payments"],
        "total_revenue": round(payment_stats["total_revenue"], 2),
        "total_refunds": round(abs(payment_stats["total_refunds"]), 2),
        "net_revenue": round(payment_stats["net_revenue"], 2),
        "completed_revenue": round(payment_stats["completed_revenue"], 2),
        "pending_payments": payment_stats["pending_payments"]
    }

    # === RECENT ACTIVITY ===
    # Recent sessions (last 10)
    recent_sessions = con.execute("""
        SELECT
            s.session_id,
            s.started,
            s.stopped,
            s.duration_minutes,
            u.username,
            pl.name as parking_lot_name,
            v.license_plate
        FROM sessions s
        LEFT JOIN users u ON s.user_id = u.id
        LEFT JOIN parking_lots pl ON s.parking_lot_id = pl.id
        LEFT JOIN vehicles v ON s.vehicle_id = v.id
        ORDER BY s.started DESC
        LIMIT 10
    """).fetchall()

    dashboard_data["recent_sessions"] = [dict(row) for row in recent_sessions]

    # Recent payments (last 10)
    recent_payments = con.execute("""
        SELECT
            p.transaction_id,
            p.amount,
            p.created_at,
            p.completed,
            u.username,
            pl.name as parking_lot_name
        FROM payments p
        LEFT JOIN users u ON p.user_id = u.id
        LEFT JOIN parking_lots pl ON p.parking_lot_id = pl.id
        ORDER BY p.created_at DESC
        LIMIT 10
    """).fetchall()

    dashboard_data["recent_payments"] = [dict(row) for row in recent_payments]

    return dashboard_data


@router.get("/users")
def list_all_users(admin=Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    """
    Get a list of all users in the system

    Returns user information (excluding passwords)
    """
    log_event("INFO", event="admin_users_list_accessed",
              message="admin_accessed_user_list",
              username=admin.get("username"))
    users = con.execute("""
        SELECT
            id,
            username,
            name,
            email,
            phone,
            role,
            created_at,
            birth_year,
            active
        FROM users
        ORDER BY created_at DESC
    """).fetchall()

    return [dict(user) for user in users]


@router.get("/users/{user_id}")
def get_user_details(user_id: int, admin=Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    """
    Get detailed information about a specific user

    Includes their vehicles, sessions, and payment history
    """
    # Get user info
    user = con.execute("""
        SELECT
            id,
            username,
            name,
            email,
            phone,
            role,
            created_at,
            birth_year,
            active
        FROM users
        WHERE id = ?
    """, (user_id,)).fetchone()

    if not user:
        log_event("WARNING", event="admin_user_details_failed",
                  message="user_not_found",
                  admin_username=admin.get("username"),
                  target_user_id=user_id)
        raise HTTPException(404, detail="User not found")

    log_event("INFO", event="admin_user_details_accessed",
              message="admin_accessed_user_details",
              admin_username=admin.get("username"),
              target_user_id=user_id,
              target_username=user["username"])

    user_data = dict(user)

    # Get user's vehicles
    vehicles = con.execute("""
        SELECT v.*
        FROM vehicles v
        JOIN user_vehicles uv ON v.id = uv.vehicle_id
        WHERE uv.user_id = ?
    """, (user_id,)).fetchall()
    user_data["vehicles"] = [dict(v) for v in vehicles]

    # Get user's sessions
    sessions = con.execute("""
        SELECT
            s.*,
            pl.name as parking_lot_name,
            v.license_plate
        FROM sessions s
        LEFT JOIN parking_lots pl ON s.parking_lot_id = pl.id
        LEFT JOIN vehicles v ON s.vehicle_id = v.id
        WHERE s.user_id = ?
        ORDER BY s.started DESC
    """, (user_id,)).fetchall()
    user_data["sessions"] = [dict(s) for s in sessions]

    # Get user's payments
    payments = con.execute("""
        SELECT
            p.*,
            pl.name as parking_lot_name
        FROM payments p
        LEFT JOIN parking_lots pl ON p.parking_lot_id = pl.id
        WHERE p.user_id = ?
        ORDER BY p.created_at DESC
    """, (user_id,)).fetchall()
    user_data["payments"] = [dict(p) for p in payments]

    return user_data


@router.get("/parking-lots/stats")
def get_parking_lot_statistics(admin=Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    """
    Get detailed statistics for each parking lot

    Includes occupancy, sessions, and revenue
    """
    log_event("INFO", event="admin_parking_stats_accessed",
              message="admin_accessed_parking_lot_statistics",
              username=admin.get("username"))
    parking_lots = con.execute("""
        SELECT
            pl.*,
            COUNT(DISTINCT s.session_id) as total_sessions,
            COUNT(DISTINCT CASE WHEN s.stopped IS NULL THEN s.session_id END) as active_sessions,
            COALESCE(SUM(p.amount), 0) as total_revenue
        FROM parking_lots pl
        LEFT JOIN sessions s ON pl.id = s.parking_lot_id
        LEFT JOIN payments p ON pl.id = p.parking_lot_id
        GROUP BY pl.id
        ORDER BY total_revenue DESC
    """).fetchall()

    result = []
    for lot in parking_lots:
        lot_dict = dict(lot)
        lot_dict["occupancy_rate"] = round(
            (lot_dict["reserved"] / lot_dict["capacity"] * 100) if lot_dict["capacity"] > 0 else 0,
            2
        )
        result.append(lot_dict)

    return result


@router.get("/sessions/active")
def get_active_sessions(admin=Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    """
    Get all currently active parking sessions
    """
    log_event("INFO", event="admin_active_sessions_accessed",
              message="admin_accessed_active_sessions",
              username=admin.get("username"))
    sessions = con.execute("""
        SELECT
            s.*,
            u.username,
            u.name as user_name,
            pl.name as parking_lot_name,
            pl.location as parking_lot_location,
            v.license_plate,
            v.make,
            v.model
        FROM sessions s
        LEFT JOIN users u ON s.user_id = u.id
        LEFT JOIN parking_lots pl ON s.parking_lot_id = pl.id
        LEFT JOIN vehicles v ON s.vehicle_id = v.id
        WHERE s.stopped IS NULL
        ORDER BY s.started DESC
    """).fetchall()

    return [dict(session) for session in sessions]


@router.get("/revenue/summary")
def get_revenue_summary(admin=Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    """
    Get revenue summary broken down by parking lot and time period
    """
    log_event("INFO", event="admin_revenue_summary_accessed",
              message="admin_accessed_revenue_summary",
              username=admin.get("username"))
    # Revenue by parking lot
    revenue_by_lot = con.execute("""
        SELECT
            pl.id,
            pl.name,
            pl.location,
            COALESCE(SUM(CASE WHEN p.amount > 0 THEN p.amount ELSE 0 END), 0) as revenue,
            COALESCE(SUM(CASE WHEN p.amount < 0 THEN p.amount ELSE 0 END), 0) as refunds,
            COUNT(p.payment_id) as payment_count
        FROM parking_lots pl
        LEFT JOIN payments p ON pl.id = p.parking_lot_id
        GROUP BY pl.id
        ORDER BY revenue DESC
    """).fetchall()

    # Top paying users
    top_users = con.execute("""
        SELECT
            u.id,
            u.username,
            u.name,
            COALESCE(SUM(p.amount), 0) as total_paid,
            COUNT(p.payment_id) as payment_count
        FROM users u
        LEFT JOIN payments p ON u.id = p.user_id
        GROUP BY u.id
        HAVING total_paid > 0
        ORDER BY total_paid DESC
        LIMIT 10
    """).fetchall()

    return {
        "revenue_by_parking_lot": [dict(row) for row in revenue_by_lot],
        "top_paying_users": [dict(row) for row in top_users]
    }


@router.get("/system/health")
def get_system_health(admin=Depends(require_admin), con: sqlite3.Connection = Depends(get_db)):
    """
    Get system health metrics

    Checks for potential issues like unpaid sessions, pending payments, etc.
    """
    log_event("INFO", event="admin_system_health_accessed",
              message="admin_accessed_system_health",
              username=admin.get("username"))
    # Sessions without payment
    unpaid_completed_sessions = con.execute("""
        SELECT COUNT(*) as count
        FROM sessions s
        LEFT JOIN payments p ON s.session_id = p.session_id
        WHERE s.stopped IS NOT NULL
        AND p.payment_id IS NULL
    """).fetchone()["count"]

    # Very long active sessions (> 7 days)
    long_active_sessions = con.execute("""
        SELECT COUNT(*) as count
        FROM sessions
        WHERE stopped IS NULL
        AND julianday('now') - julianday(started) > 7
    """).fetchone()["count"]

    # Pending payments
    pending_payments = con.execute("""
        SELECT COUNT(*) as count
        FROM payments
        WHERE completed = 0
    """).fetchone()["count"]

    # Inactive users (no sessions in last 90 days)
    inactive_users = con.execute("""
        SELECT COUNT(DISTINCT u.id) as count
        FROM users u
        LEFT JOIN sessions s ON u.id = s.user_id AND datetime(s.started) >= datetime('now', '-90 days')
        WHERE s.session_id IS NULL AND u.role = 'USER'
    """).fetchone()["count"]

    return {
        "unpaid_completed_sessions": unpaid_completed_sessions,
        "long_active_sessions": long_active_sessions,
        "pending_payments": pending_payments,
        "inactive_users": inactive_users,
        "health_status": "healthy" if (unpaid_completed_sessions == 0 and long_active_sessions == 0) else "needs_attention"
    }
