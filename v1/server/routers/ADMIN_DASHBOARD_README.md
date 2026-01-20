# Admin Dashboard API Documentation

## Overview
The Admin Dashboard provides comprehensive statistics and management capabilities for administrators of the MobyPark system. All endpoints in this module require admin authentication.

##logins
Username: admin
Wachtwoord: password

## Authentication
All admin endpoints require:
- A valid session token in the `Authorization` header
- The user's role must be `ADMIN`

If these requirements are not met, the API will return:
- `401 Unauthorized` - Missing or invalid session token
- `403 Forbidden` - Valid user but not an admin

## Endpoints

### 1. GET `/admin/dashboard`
Get comprehensive system overview with statistics about all aspects of MobyPark.

**Response Structure:**
```json
{
  "users": {
    "total": 1234,
    "admins": 5,
    "regular_users": 1229,
    "recent_new_users": 23
  },
  "parking_lots": {
    "total": 50,
    "total_capacity": 5000,
    "total_reserved": 3245,
    "available_spots": 1755,
    "occupancy_rate": 64.9
  },
  "sessions": {
    "total": 45678,
    "active": 234,
    "completed": 45444
  },
  "vehicles": {
    "total": 3456
  },
  "payments": {
    "total_payments": 12345,
    "total_revenue": 123456.78,
    "total_refunds": 1234.56,
    "net_revenue": 122222.22,
    "completed_revenue": 120000.00,
    "pending_payments": 45
  },
  "recent_sessions": [...],
  "recent_payments": [...]
}
```

**Use Case:** Main admin dashboard overview screen

---

### 2. GET `/admin/users`
Get a list of all users in the system (excludes passwords).

**Response:** Array of user objects
```json
[
  {
    "id": 1,
    "username": "john_doe",
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "1234567890",
    "role": "USER",
    "created_at": "2025-01-15",
    "birth_year": 1990,
    "active": 1
  }
]
```

**Use Case:** User management screen, viewing all system users

---

### 3. GET `/admin/users/{user_id}`
Get detailed information about a specific user including their vehicles, sessions, and payments.

**Parameters:**
- `user_id` (path): User ID

**Response:**
```json
{
  "id": 1,
  "username": "john_doe",
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "1234567890",
  "role": "USER",
  "created_at": "2025-01-15",
  "birth_year": 1990,
  "active": 1,
  "vehicles": [...],
  "sessions": [...],
  "payments": [...]
}
```

**Use Case:** User detail view, investigating specific user activity

---

### 4. GET `/admin/parking-lots/stats`
Get detailed statistics for each parking lot including occupancy, sessions, and revenue.

**Response:** Array of parking lot statistics
```json
[
  {
    "id": 1,
    "name": "City Center Parking",
    "location": "Amsterdam",
    "capacity": 200,
    "reserved": 145,
    "total_sessions": 5678,
    "active_sessions": 15,
    "total_revenue": 45678.90,
    "occupancy_rate": 72.5
  }
]
```

**Use Case:** Parking lot performance analysis, capacity planning

---

### 5. GET `/admin/sessions/active`
Get all currently active parking sessions across all parking lots.

**Response:** Array of active session objects with user, vehicle, and parking lot details
```json
[
  {
    "session_id": 123,
    "started": "20-01-2025 14:30:00",
    "stopped": null,
    "username": "john_doe",
    "user_name": "John Doe",
    "parking_lot_name": "City Center Parking",
    "parking_lot_location": "Amsterdam",
    "license_plate": "AB-123-CD",
    "make": "Toyota",
    "model": "Corolla"
  }
]
```

**Use Case:** Real-time monitoring of active parking sessions

---

### 6. GET `/admin/revenue/summary`
Get revenue summary broken down by parking lot and top paying users.

**Response:**
```json
{
  "revenue_by_parking_lot": [
    {
      "id": 1,
      "name": "City Center Parking",
      "location": "Amsterdam",
      "revenue": 45678.90,
      "refunds": 234.50,
      "payment_count": 1234
    }
  ],
  "top_paying_users": [
    {
      "id": 42,
      "username": "frequent_parker",
      "name": "Jane Smith",
      "total_paid": 5678.90,
      "payment_count": 234
    }
  ]
}
```

**Use Case:** Financial reporting, identifying top revenue sources

---

### 7. GET `/admin/system/health`
Get system health metrics to identify potential issues.

**Response:**
```json
{
  "unpaid_completed_sessions": 23,
  "long_active_sessions": 5,
  "pending_payments": 12,
  "inactive_users": 456,
  "health_status": "needs_attention"
}
```

**Metrics:**
- `unpaid_completed_sessions`: Completed sessions without any payment
- `long_active_sessions`: Sessions active for more than 7 days
- `pending_payments`: Payments not yet completed
- `inactive_users`: Users with no sessions in the last 90 days
- `health_status`: Either "healthy" or "needs_attention"

**Use Case:** System monitoring, identifying issues requiring attention

---

## Example Usage

### Using cURL

```bash
# Get dashboard overview
curl -H "Authorization: your-admin-token" http://localhost:8000/admin/dashboard

# List all users
curl -H "Authorization: your-admin-token" http://localhost:8000/admin/users

# Get specific user details
curl -H "Authorization: your-admin-token" http://localhost:8000/admin/users/123

# Get parking lot statistics
curl -H "Authorization: your-admin-token" http://localhost:8000/admin/parking-lots/stats

# Get active sessions
curl -H "Authorization: your-admin-token" http://localhost:8000/admin/sessions/active

# Get revenue summary
curl -H "Authorization: your-admin-token" http://localhost:8000/admin/revenue/summary

# Check system health
curl -H "Authorization: your-admin-token" http://localhost:8000/admin/system/health
```

### Using Python Requests

```python
import requests

admin_token = "your-admin-token-here"
headers = {"Authorization": admin_token}
base_url = "http://localhost:8000"

# Get dashboard
response = requests.get(f"{base_url}/admin/dashboard", headers=headers)
dashboard_data = response.json()
print(f"Total users: {dashboard_data['users']['total']}")
print(f"Occupancy rate: {dashboard_data['parking_lots']['occupancy_rate']}%")

# Check system health
health = requests.get(f"{base_url}/admin/system/health", headers=headers).json()
if health['health_status'] == 'needs_attention':
    print(f"Warning: {health['unpaid_completed_sessions']} unpaid sessions")
```

## Integration Tips

1. **Dashboard Refresh**: The dashboard endpoint is optimized for frequent polling. Consider refreshing every 30-60 seconds for real-time monitoring.

2. **Pagination**: Currently, the endpoints return all results. For large datasets, consider implementing pagination in the frontend.

3. **Caching**: The statistics are calculated on-demand. For high-traffic scenarios, consider implementing caching on the frontend.

4. **Health Monitoring**: Set up alerts based on the `/admin/system/health` endpoint. You can trigger notifications when `health_status` is "needs_attention".

5. **Export Data**: All endpoints return JSON data that can easily be exported to CSV or Excel for reporting purposes.

## Security Considerations

- Never expose admin tokens in client-side code
- Always use HTTPS in production
- Implement rate limiting for admin endpoints
- Log all admin actions for audit purposes
- Regularly rotate admin credentials
