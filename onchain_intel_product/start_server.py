#!/usr/bin/env python3
"""
Simple server launcher for OnChain Intelligence Data Product.
"""

import os
import sys
import uvicorn

def main():
    """Start the FastAPI server."""

    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # Add current directory to Python path
    sys.path.insert(0, script_dir)

    print("🚀 Starting OnChain Intelligence Data Product Server")
    print(f"📁 Working directory: {script_dir}")
    print("🌐 Server will be available at: http://localhost:8000")
    print("📚 API documentation: http://localhost:8000/docs")
    print("Press Ctrl+C to stop the server")
    print()

    try:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())