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

In the window, laid out as EasyEDA's part selector:
1. Choose a category on the left, with how many parts each holds, or type a part, a value or an LCSC number (*AMS1117-3.3*, *10k 0603*, *C6186*) and press Enter. **In stock** and **Basic parts only** narrow the results, Basic parts being those JLCPCB assembles without a setup fee, and **Sort** orders them by stock or price.
2. Each part is a card: its photo, its name (a link to its LCSC page), its footprint, maker, LCSC number and datasheet, its price at each quantity, its stock, and whether it is Basic or Extended.
3. Click a card to see what EasyEDA has drawn of it, symbol, footprint and 3D model, with a picture of its symbol. It is asked one part at a time: EasyEDA turns away many requests at once for a few minutes.
4. **Import** puts it into your library; **✓ In library** marks those already there, and a right-click imports one again, replacing it.

The library is `Documents/KiCad/lcsc-library/LCSC.kicad_sym`, `LCSC.pretty` and `LCSC.3dshapes`, which **Library…** changes. The first import adds it to KiCad's global symbol and footprint tables, keeping a copy of each table as `*.before-lcsc`. Restart KiCad, or open **Preferences › Manage Libraries**, to see it. In the Schematic editor, **Place › Add Symbol** then lists it as **LCSC**, each symbol with its footprint set.

## Files

| File | What it is |
| --- | --- |
| `lcsc_to_kicad/core.py` | searching, converting with easyeda2kicad, and KiCad's library tables |
| `lcsc_to_kicad/dialog.py` | the window |
| `lcsc_to_kicad/__init__.py` | the PCB editor's button |
| `run.py`, `LCSC to KiCad.bat` | the window on its own, and the command line |
| `install.py` | copies the plugin into KiCad's plugins folder; `--remove` takes it out |
