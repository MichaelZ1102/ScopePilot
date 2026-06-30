"""Delete old SQLite database."""
import pathlib, os, shutil
db_dir = pathlib.Path.home() / ".scopepilot"
if db_dir.exists():
    for f in db_dir.iterdir():
        try:
            f.unlink()
            print(f"Deleted: {f.name}")
        except Exception as e:
            print(f"Skip: {f.name}: {e}")
    try:
        db_dir.rmdir()
        print("Directory removed")
    except:
        print("Directory not empty (locked files)")
