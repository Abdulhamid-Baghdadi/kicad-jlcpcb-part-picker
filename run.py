"""LCSC parts to KiCad, on its own or from the command line.

    run.py                              opens the search window (run it with KiCad's Python, which has wx)
    run.py --schematic                  … with a button on each part that puts its symbol in KiCad's schematic editor
    run.py C6186 C25804 …               imports those LCSC parts into your library, no window
    run.py C6186 --out MyParts          makes a library of them in the folder MyParts, KiCad's settings left as they are
    run.py C6186 --out MyParts --project path/to/board
                                        … and lists it in that KiCad project's own symbol and footprint tables
    run.py --check [<folder>]           checks a library: your own, or the one in <folder>
    run.py --retire                     takes the library on this computer out of KiCad's global tables: the server's is the one
    run.py --use <folder>               tells KiCad where the server's library is, its library/lcsc/kicad, when it runs on this computer

Each part imported is checked: every pin of its symbol has a pad of its number on its footprint, and the 3D model its
footprint names is there; LCSC's record of it, its maker, part number, description and datasheet, is written into its
symbol. Exit status 0 when every part is in and checks clean, 1 when one has a problem, 2 when one could not be imported.
"""
import argparse
import os
import re
import sys
from pathlib import Path

os.environ["LCSC_TO_KICAD_STANDALONE"] = "1"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lcsc_to_kicad import core  # noqa: E402


def command_line(settings, numbers, project):
    """Imports {numbers} into the library of {settings}, then lists it in {project}'s tables, or else KiCad's global ones."""
    failed, findings = 0, []
    for lcsc in numbers:
        if core.in_library(settings, lcsc):
            print(lcsc, "is already in", settings["name"])
            continue
        try:
            said = core.convert(settings, lcsc)
        except RuntimeError as failure:
            failed += 1
            print(lcsc + ": not imported: " + str(failure), file=sys.stderr)
            continue
        found = [line for line in said if line.startswith(("PROBLEM", "NOTE"))]
        findings += found
        print(lcsc + ": imported." + "".join("\n  " + line for line in found))
    folder = core.library_paths(settings)[0]
    if project:
        print(core.add_to_project(folder, settings["name"], project))
    elif settings.get("own"):
        print("The library is in " + str(folder.resolve()) + ": add " + settings["name"] + ".kicad_sym and " + settings["name"]
              + ".pretty in KiCad's Preferences › Manage Symbol and Footprint Libraries, or give --project.")
    elif not core.registered(settings):
        print(core.register(settings))
    problems = sum(1 for line in findings if line.startswith("PROBLEM"))
    return 2 if failed else 1 if problems else 0


def main():
    parser = argparse.ArgumentParser(description="LCSC parts to KiCad: import parts into a KiCad library, checked.")
    parser.add_argument("parts", nargs="*", help="LCSC part numbers, such as C6186; none opens the window")
    parser.add_argument("--out", help="make the library in this folder, not your own, and leave KiCad's settings as they are")
    parser.add_argument("--name", help="the library's name in KiCad, and of its files (default: your library's, LCSC)")
    parser.add_argument("--project", help="a KiCad project's folder to list the library in")
    parser.add_argument("--check", nargs="?", const="", metavar="FOLDER", help="check a library: your own, or the one in FOLDER")
    parser.add_argument("--retire", action="store_true", help="take the library on this computer out of KiCad's global tables")
    parser.add_argument("--use", metavar="FOLDER", help="tell KiCad where the server's library is")
    parser.add_argument("--schematic", action="store_true", help="open the window with a button that puts parts in the schematic editor")
    arguments = parser.parse_args()
    settings = core.load_settings()
    if arguments.out:
        # A library of its own: on this computer, whatever the settings say of the server.
        settings.update(library=arguments.out, server="", own=True)
    if arguments.name:
        settings["name"] = arguments.name
    if arguments.retire:
        print(core.unregister(settings))
        return 0
    if arguments.use:
        print(core.use(settings, arguments.use))
        return 0
    if arguments.check is not None:
        folder = Path(arguments.check) if arguments.check else core.library_paths(settings)[0]
        if not (folder / (settings["name"] + ".kicad_sym")).is_file():
            parser.error(str(folder) + " holds no " + settings["name"] + ".kicad_sym")
        findings = core.check(folder, settings["name"])
        for line in findings:
            print(line)
        problems = sum(1 for line in findings if line.startswith("PROBLEM"))
        print(settings["name"] + " in " + str(folder.resolve()) + ": " + (str(problems) + " with a problem." if problems else "clean."))
        return 1 if problems else 0
    numbers = [each.strip().upper() for each in arguments.parts]
    wrong = [each for each in numbers if not re.fullmatch(r"C\d{1,12}", each)]
    if wrong:
        parser.error("an LCSC part number is a C and digits, such as C6186, not " + ", ".join(wrong))
    if numbers:
        return command_line(settings, numbers, arguments.project)
    window(arguments.schematic)
    return 0


def window(schematic=False):
    import wx
    from lcsc_to_kicad.dialog import LcscDialog
    app = wx.App()
    dialog = LcscDialog(schematic=schematic)
    dialog.ShowModal()
    dialog.Destroy()
    app.Destroy()


if __name__ == "__main__":
    sys.exit(main())
