"""LCSC parts to KiCad: a button in KiCad's PCB editor that opens the search window.

KiCad loads this folder from its plugins folder (install.py puts it there); the window itself is dialog.py, and it
runs on its own too: run.py.
"""
import os

pcbnew = None
# Run on its own (run.py sets this), the package only lends its window and its converter: no button to register.
if not os.environ.get("LCSC_TO_KICAD_STANDALONE"):
    try:
        import pcbnew
    except ImportError:  # a Python without KiCad's board module
        pcbnew = None

if pcbnew is not None:
    class LcscToKicad(pcbnew.ActionPlugin):
        def defaults(self):
            self.name = "LCSC parts to KiCad"
            self.category = "Libraries"
            self.description = "Search LCSC's parts and import their EasyEDA symbol, footprint and 3D model into your own library"
            self.show_toolbar_button = True
            self.icon_file_name = os.path.join(os.path.dirname(__file__), "icon.png")

        def Run(self):
            import wx
            from .dialog import LcscDialog
            parent = next((window for window in wx.GetTopLevelWindows() if window.GetTitle().lower().startswith("pcb editor")), None)
            dialog = LcscDialog(parent)
            dialog.Show()

    LcscToKicad().register()
