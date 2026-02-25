"""
kpp_launcher.py — Entry point for PyInstaller packaging.

This wrapper is used only when building the standalone kpp.exe.
It sets up the sys.path so the bundled kpp/ package is importable,
then delegates to the real main.py entry point.

Build command:
    pyinstaller --onefile --console --name kpp kpp_launcher.py
"""

import sys
import os

# When running as a frozen .exe, PyInstaller sets sys._MEIPASS to the
# temporary extraction directory.  We add the bundled kpp/ sub-folder
# to the front of sys.path so all interpreter modules are importable.
if getattr(sys, "frozen", False):
    base = sys._MEIPASS
else:
    base = os.path.dirname(os.path.abspath(__file__))

kpp_pkg = os.path.join(base, "kpp")
if kpp_pkg not in sys.path:
    sys.path.insert(0, kpp_pkg)

# Now import and invoke the interpreter's main() function directly.
from main import main  # noqa: E402  (main.py inside kpp/)

if __name__ == "__main__":
    main()
