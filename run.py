"""LCSC parts to KiCad, on its own or from the command line.

    run.py                    opens the search window (run it with KiCad's Python, which has wx)
    run.py C6186 C25804 …     imports those LCSC parts into your library, no window
    run.py --retire           takes the library on this computer out of KiCad's global tables: the server's is the one
"""
import os
import sys
from pathlib import Path

os.environ["LCSC_TO_KICAD_STANDALONE"] = "1"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lcsc_to_kicad import core  # noqa: E402


def command_line(numbers):
    settings = core.load_settings()
    for lcsc in numbers:
        if core.in_library(settings, lcsc):
            print(lcsc, "is already in", settings["name"])
            continue
        for line in core.convert(settings, lcsc)[-1:]:
            print(line)
    if not core.registered(settings):
        print(core.register(settings))


def window():
    import wx
    from lcsc_to_kicad.dialog import LcscDialog
    app = wx.App()
    dialog = LcscDialog()
    dialog.ShowModal()
    dialog.Destroy()
    app.Destroy()


if __name__ == "__main__":
    if sys.argv[1:] == ["--retire"]:
        print(core.unregister(core.load_settings()))
    elif len(sys.argv) > 1:
        command_line(sys.argv[1:])
    else:
        window()
