"""A part put on a board in KiCad's PCB editor: its footprint from the library KiCad finds it in, named as KiCad names it,
<library>:<footprint>, so that Update Footprints from Library finds it again; with the next free reference of its kind,
its value, and its LCSC number, maker and part number as hidden fields; in the middle of the board, beside any part
already there. It needs KiCad's own Python, which has its board module.
"""
import os

import pcbnew

from . import core

STEP = pcbnew.FromMM(5)


def place(board, settings, lcsc):
    """Puts the part {lcsc} on {board}, as above; its reference."""
    project = os.path.dirname(board.GetFileName()) or os.getcwd()
    part = core.footprint_of(settings, lcsc, project)
    footprint = pcbnew.FootprintLoad(part["folder"], part["footprint"])
    if footprint is None:
        raise RuntimeError("KiCad could not read the footprint " + part["footprint"] + " in " + part["folder"] + ".")
    footprint.SetFPID(pcbnew.LIB_ID(part["library"], part["footprint"]))
    taken = {each.GetReference() for each in board.GetFootprints()}
    number = 1
    while part["reference"] + str(number) in taken:
        number += 1
    footprint.SetReference(part["reference"] + str(number))
    footprint.SetValue(part["value"])
    for name, value in part["fields"].items():
        footprint.SetField(name, value)
        footprint.GetField(name).SetVisible(False)
    footprint.SetPosition(free_spot(board))
    board.Add(footprint)
    return footprint.GetReference()


def free_spot(board):
    """The middle of the board's outline, or of its parts when it has none, moved along until no part sits there."""
    box = board.GetBoardEdgesBoundingBox()
    held = {(each.GetPosition().x, each.GetPosition().y) for each in board.GetFootprints()}
    if box.GetWidth() > 0:
        at = box.GetCenter()
    elif held:
        xs, ys = [x for x, _ in held], [y for _, y in held]
        at = pcbnew.VECTOR2I((min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2)
    else:
        at = pcbnew.VECTOR2I(pcbnew.FromMM(100), pcbnew.FromMM(100))
    while (at.x, at.y) in held:
        at = pcbnew.VECTOR2I(at.x + STEP, at.y)
    return at
