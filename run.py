from app import create_app, db
from app.models import User
import os

app = create_app()

@app.shell_context_processor
def _shell_ctx():
    return {"db": db, "User": User}

def seed_if_needed():
    if os.environ.get("SEED_ON_STARTUP") == "1":
        with app.app_context():
            from app.seed import seed_data
            seed_data()

seed_if_needed()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
