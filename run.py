"""
Simple script to run the MobyPark API server.
Just run: python run.py
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "v1.server.app:app",
        host="localhost",
        port=8000,
        reload=True,
        log_level="info"
    )
