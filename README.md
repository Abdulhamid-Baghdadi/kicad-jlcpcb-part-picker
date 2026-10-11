# LCSC parts to KiCad

A small tool for KiCad: search LCSC's parts, as JLCPCB's parts search finds them, import those you choose into a KiCad library, Modular Electronics Studio's on the server or one of your own, and put them on the board open in the PCB editor. Each part comes as EasyEDA has drawn it:
- its symbol, with its footprint already set and its LCSC number;
- its footprint;
- its 3D model, as STEP where there is one, so that KiCad's STEP export has it;
- LCSC's record of it in its symbol, as hidden fields: its maker, part number, description and datasheet; its prices and stock in `records.json` beside the library.

Each part imported is checked, as the studio checks its own library: every pin of its symbol has a pad of its number on its footprint, and the 3D model its footprint names is there. EasyEDA draws some parts' symbols and footprints apart; the check says so (*PROBLEM C2927039 USB-TYPE-C-019: pins 1, A1, A12, A4, A9 have no pad…*), and a pad no pin names, such as a shield, is noted.

KiCad's own library does not tie a symbol to one footprint; here every part is a symbol and its footprint together, and one JLCPCB can assemble.

## What it needs

- **KiCad 8 or later.** Its Python runs the window, and its PCB editor shows the button.
- **Python with easyeda2kicad**, which does the conversion (AGPL-3.0, not copied here):

  ```
  python -m pip install easyeda2kicad
  ```

  The tool finds that Python on the PATH, or you name it as `"python"` in `~/.lcsc-to-kicad.json`.
- **Internet access**, to JLCPCB's parts search and EasyEDA's part data. Both are the websites' own, unofficial, endpoints, and may change.

## In the schematic editor

KiCad shows its older Python plugins, such as this tool's button, only in the PCB editor. For the schematic editor, `install.py` also installs a button of KiCad's newer kind (`schematic/`, in `Documents/KiCad/<version>/plugins/lcsc-to-kicad`), which opens the same window with KiCad's own Python. KiCad shows such buttons once its API is on: **Preferences › Preferences… › Plugins › Enable KiCad API**, then restart KiCad. The first start after installing makes the button a Python environment of its own, which takes a few seconds; the button shows in schematic editors opened after that. In the schematic editor the window imports parts; **Place › Add Symbol** then finds them in the library **LCSC**.

## Using it

- **In KiCad's PCB editor:** run `python install.py` once, then in the PCB editor **Tools › External Plugins › Refresh Plugins**; the button **LCSC parts to KiCad** is on the top toolbar, among the plugins. To have the plugins' buttons on the right toolbar, beside the drawing tools, as KiCad 10 lets you arrange its toolbars: open **Preferences › Preferences… › PCB Editor › Toolbars** once and press **OK**, so that KiCad writes them down, then run `python install.py --sidebar` and restart KiCad (`--no-sidebar` puts them back; the files before are kept as `*.before-lcsc`).
- **On its own:** double-click `LCSC to KiCad.bat` (Windows), or run `run.py` with KiCad's Python.
- **From the command line:** `python run.py C6186 C25804` imports those parts without the window; `python run.py C6186 --out MyParts` makes a library of them in the folder `MyParts`, leaving KiCad's settings as they are, and `--project <board folder>` lists it in that project's own symbol and footprint tables; `python run.py --check [<folder>]` checks a library, yours or the one in the folder; `python run.py --retire` takes a library kept on this computer out of KiCad's global tables, and `python run.py --use <folder>` points them at the server's (below).

In the window, laid out as EasyEDA's part selector:
1. Choose a category on the left, with how many parts each holds, or type a part, a value or an LCSC number (*AMS1117-3.3*, *10k 0603*, *C6186*) and press Enter. **In stock** and **Basic parts only** narrow the results, Basic parts being those JLCPCB assembles without a setup fee, and **Sort** orders them by stock or price.
2. Each part is a card: its photo, its name (a link to its LCSC page), its footprint, maker, LCSC number and datasheet, its price at each quantity, its stock, and whether it is Basic or Extended.
3. Click a card to see what EasyEDA has drawn of it, symbol, footprint and 3D model, with a picture of its symbol. It is asked one part at a time: EasyEDA turns away many requests at once for a few minutes.
4. **Import** puts it into your library; **✓ In library** marks those already there, and a right-click imports one again, replacing it.
5. Opened from the PCB editor, **Place on board** puts it on the open board, imported first when it is not yet in the library: its footprint, named by its library (`LCSC:…`, so that **Update Footprints from Library** finds it), with the next free reference of its kind, its value and its LCSC number, maker and part number as hidden fields, in the middle of the board, beside the parts already there. Close the window to move it. A symbol cannot be put on the schematic this way: KiCad gives plugins no way into its schematic editor.

## Where the parts go

**Library…** asks for the desktop link that Modular Electronics Studio's page gives (**Connect a desktop program…**). With it, each part is converted on the server and goes into its LCSC library, `library/lcsc/kicad`: its symbol, footprint and 3D model, and an element of its own, whose pins are its ports, with the part's record from LCSC. The page's **Parts from LCSC…** adds parts to the same library. Every KiCad project the server writes takes the library along in its `libraries/` folder, listed as **LCSC** in the project's own symbol and footprint tables, so KiCad needs no global library.

Without a link, the tool keeps a library on this computer, as it did before: `Documents/KiCad/lcsc-library/LCSC.kicad_sym`, `LCSC.pretty` and `LCSC.3dshapes`, added to KiCad's global symbol and footprint tables at the first import (copies kept as `*.before-lcsc`). To move to the server's library, give **Library…** the link, and run `python run.py --retire`: it takes **LCSC** out of KiCad's global tables, keeping copies as `*.before-retire`, so that a project's own **LCSC**, the server's, is the one KiCad finds. The folder on this computer is then no longer used; delete it when you like.

When the server runs on this computer, KiCad can use its library directly, in any project, not only those the server writes: `python run.py --use "<repository>/library/lcsc/kicad"` sets KiCad's path variable `LCSC_LIBRARY` to that folder, by which the library's footprints name their 3D models, and lists **LCSC** in KiCad's global symbol and footprint tables by it (`${LCSC_LIBRARY}/LCSC.kicad_sym` and `LCSC.pretty`), keeping the files before as `*.before-use`. Restart KiCad to see it. A project's own **LCSC**, the copy in its `libraries/` folder, still comes first in that project.

## Files

| File | What it is |
| --- | --- |
| `lcsc_to_kicad/core.py` | searching, converting with easyeda2kicad, LCSC's record, the check, where KiCad finds a footprint, and KiCad's library tables |
| `lcsc_to_kicad/place.py` | putting a part on the board, with KiCad's Python |
| `lcsc_to_kicad/dialog.py` | the window |
| `lcsc_to_kicad/__init__.py` | the PCB editor's button |
| `run.py`, `LCSC to KiCad.bat` | the window on its own, and the command line |
| `install.py` | copies the plugin into KiCad's plugins folder, and the schematic editor's button into KiCad's API plugins folder; `--remove` takes both out; `--sidebar` moves the plugins' buttons to the right toolbar |
| `schematic/` | the schematic editor's button: `plugin.json`, `open_window.py`, which opens the window with KiCad's Python, and `requirements.txt`, empty, which KiCad needs before it shows the button |
