"""The schematic editor's button: opens the LCSC parts window, as run.py --schematic does, with a button on each part
that puts its symbol on the schematic; with KiCad's own Python, which has the window's toolkit (wx), apart from the
plugin's environment KiCad runs this in. install.py puts run.py and the lcsc_to_kicad package beside it."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def kicad_python():
    """KiCad's own Python: the one this plugin's environment was made from, its windowless form on Windows."""
    for folder in (sys.base_prefix, os.path.dirname(sys.executable)):
        for name in ("pythonw.exe", "python.exe", "python3", "python"):
            candidate = os.path.join(folder, name)
            if os.path.isfile(candidate):
                return candidate
    return sys.executable


# Without what this environment sets for itself, which would lead KiCad's Python astray
environment = {key: value for key, value in os.environ.items()
               if key.upper() not in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "PYTHONEXECUTABLE", "__PYVENV_LAUNCHER__")}
flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
subprocess.Popen([kicad_python(), os.path.join(HERE, "run.py"), "--schematic"], cwd=HERE, env=environment, creationflags=flags, close_fds=True)
