"""
StadiumMind AI — Development Server Entry Point
Run with: python run.py
"""

import os

from app import create_app
from app.config import Config

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    print("\n🏟️  StadiumMind AI — FIFA World Cup 2026")
    print(f"   Running at: http://localhost:{port}")
    print(f"   Debug mode: {debug}")
    print(f"   Mock AI:    {app.config.get('MOCK_AI', Config.MOCK_AI)}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
