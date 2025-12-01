# MobyPark API Tests

Local tests using FastAPI's TestClient. No web server needed!

## Test Files

### `test_with_testclient.py`
Comprehensive test script that tests all 27 endpoints with detailed output.

**Run:**
```bash
cd v1
python tests/test_with_testclient.py
```

**Features:**
- Tests all endpoints sequentially
- Shows detailed request/response for each test
- Creates test users, vehicles, parking lots, sessions, payments, and reservations
- No server needed - uses TestClient directly

### `test_endpoints.py`
Professional pytest test suite with organized test cases.

**Run:**
```bash
cd v1
pip install pytest  # if not installed
pytest tests/test_endpoints.py -v
```

**Features:**
- 25+ organized test cases
- Uses pytest fixtures for setup
- Shows pass/fail summary
- Professional test structure

**Advanced pytest commands:**
```bash
# Show detailed output
pytest tests/test_endpoints.py -v -s

# Run specific test class
pytest tests/test_endpoints.py::TestAuthentication -v

# Run specific test
pytest tests/test_endpoints.py::TestAuthentication::test_login_success -v

# Stop at first failure
pytest tests/test_endpoints.py -x

# Show coverage
pytest tests/test_endpoints.py --cov=server --cov-report=html
```

## What Gets Tested

- **Authentication** (7 tests): Register, login, profile, logout
- **Vehicles** (5 tests): Create, list, update, delete vehicles
- **Parking Lots** (3 tests): List, get details, create (admin)
- **Parking Sessions** (3 tests): Start, stop, list sessions
- **Payments** (3 tests): Create, complete, list payments
- **Reservations** (4 tests): Create, get, update, delete reservations

## Requirements

The tests use FastAPI's TestClient, which:
- ✅ Runs without starting the server
- ✅ Faster than HTTP requests
- ✅ Easier to debug
- ✅ Official recommended approach

## Database

Tests will automatically:
1. Use the existing database at `Database/MobyPark.db`
2. Create test users and data
3. Clean up after themselves (mostly)

If you want a fresh database for testing:
```bash
cd v1
rm Database/MobyPark.db
python Database/database_creation.py
```

## Troubleshooting

### ModuleNotFoundError
Make sure you're running from the v1 directory:
```bash
cd v1
python tests/test_with_testclient.py
```

### Database errors
Recreate the database:
```bash
cd v1
rm Database/MobyPark.db
python Database/database_creation.py
```

### pytest not found
Install pytest:
```bash
pip install pytest
```

## Example Output

### test_with_testclient.py
```
MobyPark API Testing with TestClient
======================================================================
No need to run the server separately!
======================================================================

1  Testing: POST /register
======================================================================
>>> Register User
======================================================================
Status: 200 OK
Response:
{
  "message": "User created"
}

 All tests completed!
```

### test_endpoints.py
```
tests/test_endpoints.py::TestAuthentication::test_register_new_user PASSED  [ 4%]
tests/test_endpoints.py::TestAuthentication::test_login_success PASSED      [ 8%]
tests/test_endpoints.py::TestVehicles::test_create_vehicle PASSED           [12%]
...
======================== 25 passed in 2.34s ==========================
```

## Tips

1. Run `test_with_testclient.py` for detailed debugging
2. Run `test_endpoints.py` for quick pass/fail summary
3. Both tests work without starting the server
4. Tests create their own test data
5. Check the output for any failed tests
