"""
StadiumMind AI — Development Server Entry Point
Run with: python run.py
"""
import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    print(f"\n🏟️  StadiumMind AI — FIFA World Cup 2026")
    print(f"   Running at: http://localhost:{port}")
    print(f"   Debug mode: {debug}")
    print(f"   Mock AI:    {os.environ.get('MOCK_AI', 'false')}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
