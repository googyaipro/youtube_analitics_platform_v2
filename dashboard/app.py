import os

# Forwarding wrapper to 0_🏠_Главная.py
main_page_path = os.path.join(os.path.dirname(__file__), "0_🏠_Главная.py")
with open(main_page_path, "r", encoding="utf-8") as f:
    code = compile(f.read(), main_page_path, "exec")
    exec(code, globals())
