"""Puts the plugin where KiCad's PCB editor finds it: a copy of lcsc_to_kicad in KiCad's plugins folder.

    python install.py          installs, or updates, the plugin for the newest KiCad
    python install.py --remove takes it out again

Then, in the PCB editor, Tools › External Plugins › Refresh Plugins, and its button appears on the toolbar.
"""
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def plugins_folder():
    """KiCad's plugins folder in your documents, for its newest version: Documents/KiCad/<version>/scripting/plugins."""
    documents = Path(os.environ.get("KICAD_DOCUMENTS_HOME", Path.home() / "Documents" / "KiCad"))
    versions = sorted((path for path in documents.glob("*") if path.is_dir() and re.fullmatch(r"\d+\.\d+", path.name)),
                      key=lambda path: [int(number) for number in path.name.split(".")])
    if not versions:
        sys.exit("KiCad's folder was not found in " + str(documents) + ": start KiCad once, then run this again.")
    return versions[-1] / "scripting" / "plugins"


def main():
    target = plugins_folder() / "lcsc_to_kicad"
    if target.exists():
        shutil.rmtree(target)
    if "--remove" in sys.argv:
        print("Removed the plugin from", target.parent)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(HERE / "lcsc_to_kicad", target, ignore=shutil.ignore_patterns("__pycache__"))
    print("Installed the plugin in", target)
    print("In KiCad's PCB editor: Tools › External Plugins › Refresh Plugins; its button is then on the toolbar.")


if __name__ == "__main__":
    main()
