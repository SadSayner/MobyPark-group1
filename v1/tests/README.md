# MobyPark API Tests

## Test Structure

Tests are organized by feature/endpoint:

- `conftest.py` - Shared fixtures and test data
- `test_auth.py` - Authentication endpoints
- `test_vehicles.py` - Vehicle CRUD operations
- `test_parking_lots.py` - Parking lot management
- `test_reservations.py` - Reservation operations
- `test_payments.py` - Payment operations
- `test_sessions.py` - Parking session management

## Running Tests

### Run all tests:
```bash
python run_tests.py
```

### Run specific test file:
```bash
python run_tests.py auth
python run_tests.py vehicles
```

## Fixes Applied

1. Added email and phone fields (required by database)
2. Fixed pytest.time.time() to time.time()
3. Split tests into separate files
4. Created shared fixtures in conftest.py
