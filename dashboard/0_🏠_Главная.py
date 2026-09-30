import os

# Forwarding entrypoint to app.py router
app_path = os.path.join(os.path.dirname(__file__), "app.py")
with open(app_path, "r", encoding="utf-8") as f:
    code = compile(f.read(), app_path, "exec")
    exec(code, globals())
