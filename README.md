# LCSC parts to KiCad

A small tool for KiCad: search LCSC's parts, as JLCPCB's parts search finds them, and import those you choose into Product Architecture Studio's LCSC library, the one copy, on the server. Each part comes as EasyEDA has drawn it:
- its symbol, with its footprint already set and its LCSC number;
- its footprint;
- its 3D model, as STEP where there is one, so that KiCad's STEP export has it.

KiCad's own library does not tie a symbol to one footprint; here every part is a symbol and its footprint together, and one JLCPCB can assemble.

## What it needs

- **KiCad 8 or later.** Its Python runs the window, and its PCB editor shows the button.
- **Python with easyeda2kicad**, which does the conversion (AGPL-3.0, not copied here):

  ```
  python -m pip install easyeda2kicad
  ```

  The tool finds that Python on the PATH, or you name it as `"python"` in `~/.lcsc-to-kicad.json`.
- **Internet access**, to JLCPCB's parts search and EasyEDA's part data. Both are the websites' own, unofficial, endpoints, and may change.

## Using it

- **In KiCad's PCB editor:** run `python install.py` once, then in the PCB editor **Tools › External Plugins › Refresh Plugins**; the button **LCSC parts to KiCad** is on the toolbar.
- **On its own:** double-click `LCSC to KiCad.bat` (Windows), or run `run.py` with KiCad's Python.
- **From the command line:** `python run.py C6186 C25804` imports those parts without the window; `python run.py --retire` takes a library kept on this computer out of KiCad's global tables (below).

In the window, laid out as EasyEDA's part selector:
1. Choose a category on the left, with how many parts each holds, or type a part, a value or an LCSC number (*AMS1117-3.3*, *10k 0603*, *C6186*) and press Enter. **In stock** and **Basic parts only** narrow the results, Basic parts being those JLCPCB assembles without a setup fee, and **Sort** orders them by stock or price.
2. Each part is a card: its photo, its name (a link to its LCSC page), its footprint, maker, LCSC number and datasheet, its price at each quantity, its stock, and whether it is Basic or Extended.
3. Click a card to see what EasyEDA has drawn of it, symbol, footprint and 3D model, with a picture of its symbol. It is asked one part at a time: EasyEDA turns away many requests at once for a few minutes.
4. **Import** puts it into your library; **✓ In library** marks those already there, and a right-click imports one again, replacing it.

## Where the parts go

**Library…** asks for the desktop link that Product Architecture Studio's page gives (**Connect a desktop program…**). With it, each part is converted on the server and goes into its LCSC library, `library/lcsc/kicad`: its symbol, footprint and 3D model, and an element of its own, whose pins are its ports, with the part's record from LCSC. The page's **Parts from LCSC…** adds parts to the same library. Every KiCad project the server writes takes the library along in its `libraries/` folder, listed as **LCSC** in the project's own symbol and footprint tables, so KiCad needs no global library.

Without a link, the tool keeps a library on this computer, as it did before: `Documents/KiCad/lcsc-library/LCSC.kicad_sym`, `LCSC.pretty` and `LCSC.3dshapes`, added to KiCad's global symbol and footprint tables at the first import (copies kept as `*.before-lcsc`). To move to the server's library, give **Library…** the link, and run `python run.py --retire`: it takes **LCSC** out of KiCad's global tables, keeping copies as `*.before-retire`, so that a project's own **LCSC**, the server's, is the one KiCad finds. The folder on this computer is then no longer used; delete it when you like.

## Files

| File | What it is |
| --- | --- |
| `lcsc_to_kicad/core.py` | searching, converting with easyeda2kicad, and KiCad's library tables |
| `lcsc_to_kicad/dialog.py` | the window |
| `lcsc_to_kicad/__init__.py` | the PCB editor's button |
| `run.py`, `LCSC to KiCad.bat` | the window on its own, and the command line |
| `install.py` | copies the plugin into KiCad's plugins folder; `--remove` takes it out |
