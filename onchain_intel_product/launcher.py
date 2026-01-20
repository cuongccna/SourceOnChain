#!/usr/bin/env python3
"""
Launcher script that must be run from onchain_intel_product directory.
"""

import os
import sys

def main():
    """Launch the server."""
    current_dir = os.getcwd()
    script_dir = os.path.dirname(os.path.abspath(__file__))

    print(f"Current directory: {current_dir}")
    print(f"Script directory: {script_dir}")

    if current_dir != script_dir:
        print(f"Changing to script directory: {script_dir}")
        os.chdir(script_dir)

    # Add current directory to path
    sys.path.insert(0, os.getcwd())

    print("Starting OnChain Intelligence Data Product Server")
    print("Server will be available at: http://localhost:8000")
    print("API documentation: http://localhost:8000/docs")
    print("Press Ctrl+C to stop the server")
    print()

    try:
        # Import and run the app
        from main import app
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())