"""A part put on a schematic in KiCad's schematic editor. KiCad's API cannot add to a schematic yet, but the editor pastes
a piece of schematic from the clipboard and hangs it on the cursor, to be put down with a click, as Place › Add Symbol
does: so the part's symbol goes there as such a piece, named as KiCad names it, <library>:<symbol>, with its drawing
along, its reference to be numbered (U?), its value, footprint and LCSC record as in the library. On Windows the editor
is brought forward and pasted into; elsewhere, or when it cannot be brought forward, Ctrl+V there pastes it.
"""
import re
import sys
import time
import uuid

import wx

from . import core

# Where the symbol stands in the piece; KiCad moves it to the cursor as it pastes. On its 1.27 mm grid.
AT = (101.6, 101.6)


def fragment(settings, lcsc, project=None):
    """The piece of schematic holding the part {lcsc}'s symbol, as text, as above."""
    block, version = core.symbol_of(settings, lcsc, project)
    name = core.first_string(block)
    library = settings["name"] + ":" + name
    drawing = block.replace(core._quote(name), core._quote(library), 1)
    letters = re.sub(r"[^A-Za-z#]", "", core.prop(block, "Reference")) or "U"
    fields = []
    for start, end in core.blocks(block, "property"):
        field = block[start:end]
        if core.first_string(field).startswith("ki_"):
            continue  # the library's own keywords and description, not a placed symbol's fields
        if core.first_string(field) == "Reference":
            field = re.sub(r'(\(property\s+"Reference"\s+)"(?:[^"\\]|\\.)*"', lambda match: match.group(1) + core._quote(letters + "?"), field, count=1)
        # A field stands where the drawing puts it, from the symbol's origin; the drawing's y points up, the sheet's down.
        field = re.sub(r"\(at\s+(-?[\d.]+)\s+(-?[\d.]+)((?:\s+-?[\d.]+)?)\)",
                       lambda match: "(at {:g} {:g}{})".format(AT[0] + float(match.group(1)), AT[1] - float(match.group(2)), match.group(3)),
                       field, count=1)
        fields.append("    " + field)
    # As KiCad copies a selection: no file header, its symbols' drawings, then the items.
    return ("(lib_symbols\n  {}\n)\n"
            "(symbol (lib_id {}) (at {:g} {:g} 0) (unit 1) (in_bom yes) (on_board yes) (uuid {})\n{}\n)\n"
            ).format(drawing, core._quote(library), AT[0], AT[1], core._quote(str(uuid.uuid4())), "\n".join(fields))


def to_clipboard(text):
    """Puts {text} on the clipboard, kept there after the window closes; whether it could."""
    if not wx.TheClipboard.Open():
        return False
    try:
        wx.TheClipboard.SetData(wx.TextDataObject(text))
        wx.TheClipboard.Flush()
    finally:
        wx.TheClipboard.Close()
    return True


def into_editor():
    """Brings KiCad's schematic editor forward and pastes there, on Windows; whether it could."""
    if not sys.platform.startswith("win"):
        return False
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(window, _):
        if user32.IsWindowVisible(window):
            length = user32.GetWindowTextLengthW(window)
            title = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(window, title, length + 1)
            if title.value.endswith("Schematic Editor"):
                found.append(window)
        return True

    # Windows are listed front first: the editor last used is the one pasted into.
    user32.EnumWindows(each, 0)
    if not found:
        return False
    if user32.IsIconic(found[0]):
        user32.ShowWindow(found[0], 9)
    user32.SetForegroundWindow(found[0])
    time.sleep(0.3)
    # Windows lets a program bring another forward only while it is itself in front; Ctrl+V goes nowhere else.
    if user32.GetForegroundWindow() != found[0]:
        return False
    control, v, up = 0x11, 0x56, 2
    for key, flags in ((control, 0), (v, 0), (v, up), (control, up)):
        user32.keybd_event(key, 0, flags, 0)
    return True
