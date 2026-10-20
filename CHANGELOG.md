# Changelog

## 1.0.0 — 2026-10-20

First release as its own repository; it was written as a tool of Modular Electronics Studio (September–October 2026).

**What it does**
- A part selector like EasyEDA's, opened from a button in KiCad's PCB editor and, with KiCad's API on, in the schematic editor; also on its own (`LCSC to KiCad.bat`, `run.py`).
- Search LCSC/JLCPCB by part, value or LCSC number, or browse its categories; filter in stock and Basic parts; sort by stock or price.
- Import a part's symbol, footprint and 3D model (STEP where there is one) with easyeda2kicad into a KiCad library of your own, with LCSC's record in the symbol and `records.json`.
- Check each part imported: every pin has a pad, and the footprint's 3D model is there.
- **Place on board**, with the next free reference; **Place on schematic**, the symbol hanging on the cursor.
- Command line: `run.py C6186 …`, `--out`, `--project`, `--check`, `--retire`, `--use`.

**Fixed for this release**
- Importing said *"easyeda2kicad was not found"* when KiCad had been started from a terminal: the converter's commands now get their own stdin.
- `run.py --out` with a relative folder left footprints naming their 3D models by that relative path, which KiCad does not find; `--check` now reports such a model.
- `LCSC to KiCad.bat` picked KiCad 9.0 over 10.0 when both were installed.
