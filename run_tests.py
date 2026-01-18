"""
Simple script to run all tests.
Just run: python run_tests.py

Run specific test files:
  python run_tests.py auth         # Run only auth tests
  python run_tests.py vehicles     # Run only vehicle tests
  python run_tests.py parking_lots # Run only parking lot tests
    python run_tests.py e2e          # Run end-to-end tests (starts API server)
"""
import pytest
import sys

if __name__ == "__main__":
    # Check if specific test file requested
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        if test_name == "e2e":
            test_path = "e2e/"
        else:
            test_path = f"v1/tests/test_{test_name}.py"
        print(f"Running {test_name} tests...")
        exit_code = pytest.main([
            test_path,
            "-v",
            "-s",
            "--tb=short",
        ])
    else:
        # Run all tests
        print("Running all tests...")
        exit_code = pytest.main([
            "v1/tests/",
            "-v",
            "-s",
            "--tb=short",
        ])

    sys.exit(exit_code)
