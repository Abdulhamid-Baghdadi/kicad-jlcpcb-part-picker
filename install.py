"""Puts the plugin where KiCad finds it: a copy of lcsc_to_kicad in KiCad's plugins folder, for the PCB editor's button;
and, for the schematic editor's, the folder schematic (with run.py and lcsc_to_kicad beside it) in the folder of
KiCad's API plugins, which KiCad shows once its API is on (Preferences › Plugins › Enable KiCad API).

    python install.py              installs, or updates, the plugin for the newest KiCad
    python install.py --remove     takes it out again
    python install.py --sidebar    moves the plugins' buttons to the PCB editor's right toolbar, beside the drawing tools (KiCad 10)
    python install.py --no-sidebar puts them back on its top toolbar

Then, in the PCB editor, Tools › External Plugins › Refresh Plugins, and its button appears on the toolbar.
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ["LCSC_TO_KICAD_STANDALONE"] = "1"
sys.path.insert(0, str(HERE))
from lcsc_to_kicad import core  # noqa: E402

# The PCB editor's control that holds the Python console's button and every plugin's.
PLUGINS = {"name": "control.IPCPlugin", "type": "CONTROL"}


def plugins_folder():
    """KiCad's plugins folder in your documents, for its newest version: Documents/KiCad/<version>/scripting/plugins."""
    return kicad_folder() / "scripting" / "plugins"


def api_plugins_folder():
    """The folder of KiCad's API plugins, for its newest version: Documents/KiCad/<version>/plugins."""
    return kicad_folder() / "plugins"


def kicad_folder():
    """KiCad's folder in your documents, for its newest version: Documents/KiCad/<version>."""
    documents = Path(os.environ.get("KICAD_DOCUMENTS_HOME", Path.home() / "Documents" / "KiCad"))
    versions = sorted((path for path in documents.glob("*") if path.is_dir() and re.fullmatch(r"\d+\.\d+", path.name)),
                      key=lambda path: [int(number) for number in path.name.split(".")])
    if not versions:
        sys.exit("KiCad's folder was not found in " + str(documents) + ": start KiCad once, then run this again.")
    return versions[-1]


def sidebar(on):
    """Moves the PCB editor's plugin buttons, the Python console's and every plugin's, to its right toolbar, beside the
    drawing tools, when {on}; else back to its top toolbar. KiCad 10 keeps its toolbars in toolbars/pcbnew-toolbars.json
    once its Preferences › PCB Editor › Toolbars has been opened; this moves the one control there, and turns custom
    toolbars on, each file kept first as *.before-lcsc. What was done, in words."""
    config = core.kicad_config()
    toolbars = config / "toolbars" / "pcbnew-toolbars.json" if config else None
    try:
        data = json.loads(toolbars.read_text(encoding="utf-8"))
    except (AttributeError, OSError, ValueError):
        data = {}
    found = {each.get("name"): each for each in data.get("toolbars") or []}
    if "RIGHT" not in found or "TOP_MAIN" not in found:
        sys.exit("KiCad has not written the PCB editor's toolbars yet. In the PCB editor, open Preferences › Preferences…,"
                 " PCB Editor › Toolbars, press OK, then run this again.")
    source, target = (found["TOP_MAIN"], found["RIGHT"]) if on else (found["RIGHT"], found["TOP_MAIN"])
    source["contents"] = [item for item in source["contents"] if item.get("name") != PLUGINS["name"]]
    while source["contents"] and source["contents"][-1].get("type") == "SEPARATOR":
        source["contents"].pop()
    if not any(item.get("name") == PLUGINS["name"] for item in target["contents"]):
        target["contents"] += [{"type": "SEPARATOR"}, dict(PLUGINS)]
    shutil.copyfile(toolbars, toolbars.with_name(toolbars.name + ".before-lcsc"))
    toolbars.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    settings = config / "pcbnew.json"
    editor = json.loads(settings.read_text(encoding="utf-8"))
    if not (editor.get("appearance") or {}).get("custom_toolbars"):
        shutil.copyfile(settings, settings.with_name("pcbnew.json.before-lcsc"))
        editor.setdefault("appearance", {})["custom_toolbars"] = True
        settings.write_text(json.dumps(editor, indent=2) + "\n", encoding="utf-8")
    return ("The plugins' buttons are now on the PCB editor's " + ("right toolbar, below the drawing tools" if on else "top toolbar")
            + ": restart KiCad to see them.")


def main():
    if "--sidebar" in sys.argv or "--no-sidebar" in sys.argv:
        print(sidebar("--sidebar" in sys.argv))
        return
    target, schematic = plugins_folder() / "lcsc_to_kicad", api_plugins_folder() / "lcsc-to-kicad"
    for folder in (target, schematic):
        if folder.exists():
            shutil.rmtree(folder)
    if "--remove" in sys.argv:
        print("Removed the plugin from", target.parent, "and", schematic.parent)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(HERE / "lcsc_to_kicad", target, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(HERE / "schematic", schematic, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(HERE / "lcsc_to_kicad", schematic / "lcsc_to_kicad", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(HERE / "run.py", schematic / "run.py")
    shutil.copyfile(HERE / "lcsc_to_kicad" / "icon.png", schematic / "icon.png")
    print("Installed the plugin in", target, "and", schematic)
    print("In KiCad's PCB editor: Tools › External Plugins › Refresh Plugins; its button is then on the toolbar.")
    print("In the schematic editor, its button shows once KiCad's API is on: Preferences › Plugins › Enable KiCad API.")
    print("To have it on the right toolbar, beside the drawing tools: python install.py --sidebar")


if __name__ == "__main__":
    main()
