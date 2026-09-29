# LCSC parts to KiCad

A small tool, apart from Product Architecture Studio, for KiCad: search LCSC's parts, as JLCPCB's parts search finds them, and import those you choose into a KiCad library of your own. Each part comes as EasyEDA has drawn it:
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
- **From the command line:** `python run.py C6186 C25804` imports those parts without the window.

In the window:
1. Type a part, a value or an LCSC number (*AMS1117-3.3*, *10k 0603*, *C6186*) and press Enter. The results show the maker, package, stock and price, and whether it is a *Basic* part, which JLCPCB assembles without a setup fee; tick **Basic parts only** to see only those.
2. Select a part to see what EasyEDA has of it: symbol, footprint and 3D model. **Datasheet** and **LCSC page** open them in your browser.
3. Double-click it, or select several and press **Import selected**. Each is converted into your library; **In library** says which already are, and **Replace…** converts them again.

The library is `Documents/KiCad/lcsc-library/LCSC.kicad_sym`, `LCSC.pretty` and `LCSC.3dshapes`, which **Library…** changes. The first import adds it to KiCad's global symbol and footprint tables, keeping a copy of each table as `*.before-lcsc`. Restart KiCad, or open **Preferences › Manage Libraries**, to see it. In the Schematic editor, **Place › Add Symbol** then lists it as **LCSC**, each symbol with its footprint set.

## Files

| File | What it is |
| --- | --- |
| `lcsc_to_kicad/core.py` | searching, converting with easyeda2kicad, and KiCad's library tables |
| `lcsc_to_kicad/dialog.py` | the window |
| `lcsc_to_kicad/__init__.py` | the PCB editor's button |
| `run.py`, `LCSC to KiCad.bat` | the window on its own, and the command line |
| `install.py` | copies the plugin into KiCad's plugins folder; `--remove` takes it out |
