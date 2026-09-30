"""LCSC parts to a KiCad library: search JLCPCB's parts, and convert a part's EasyEDA symbol, footprint and 3D model into
one library of your own, which KiCad's Schematic and PCB editors then both find.

The search asks JLCPCB's parts search, as its website does; the conversion is easyeda2kicad's (AGPL-3.0), run with a
Python that has it installed (pip install easyeda2kicad). Nothing here needs KiCad's own Python but the window.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SEARCH = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
EASYEDA = "https://easyeda.com/api/products/{}/components?version=6.4.19.5"
FILE = "https://jlcpcb.com/api/file/downloadByFileSystemAccessId/{}"
SETTINGS = Path.home() / ".lcsc-to-kicad.json"
AGENT = "lcsc-to-kicad (KiCad library tool)"


# ——— Settings ———

def default_settings():
    return {
        "library": str(Path.home() / "Documents" / "KiCad" / "lcsc-library"),
        "name": "LCSC",
        "python": "",
        # The desktop link Product Architecture Studio's page gives (Connect a desktop program…): parts then go into the
        # server's LCSC library, the one copy, which every KiCad project written from it takes along.
        "server": "",
    }


def to_server(settings):
    """Whether parts go to Product Architecture Studio's server, rather than into a library on this computer."""
    return bool((settings.get("server") or "").strip())


def _server(settings, method, path, body=None):
    link = settings["server"].strip().rstrip("/")
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(link + "/" + path, data=data, method=method, headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as failure:
        try:
            message = json.loads(failure.read().decode("utf-8")).get("error", str(failure))
        except ValueError:
            message = str(failure)
        raise RuntimeError("The server says: " + message)
    except OSError as failure:
        raise RuntimeError("The server cannot be reached: " + str(failure))


def load_settings():
    settings = default_settings()
    try:
        settings.update(json.loads(SETTINGS.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return settings


def save_settings(settings):
    SETTINGS.write_text(json.dumps(settings, indent=2), encoding="utf-8")


# ——— Searching ———

def _post(url, body, timeout=20):
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _get(url, timeout=20):
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


SORTS = {"Relevance": None, "Stock, most first": ("STOCK_SORT", "DESC"), "Price, lowest first": ("PRICE_SORT", "ASC"),
         "Price, highest first": ("PRICE_SORT", "DESC")}


def search(keyword, page=1, size=20, category=None, subcategory=None, basic=False, in_stock=False, sort=None):
    """Parts matching {keyword} (a name, a value or an LCSC number such as C6186; empty for all) in {category} or its
    {subcategory}, Basic parts only, in stock only, sorted as {sort} names one of SORTS: (total, parts), each a dict."""
    body = {"keyword": keyword, "currentPage": page, "pageSize": size}
    if subcategory:
        body["secondSortName"] = subcategory
    elif category:
        body["firstSortName"] = category
    if basic:
        body["componentLibraryType"] = "base"
    if in_stock:
        body["stockFlag"] = True
    if SORTS.get(sort):
        body["sortMode"], body["sortASC"] = SORTS[sort]
    answer = _post(SEARCH, body)
    info = ((answer or {}).get("data") or {}).get("componentPageInfo") or {}
    parts = []
    for item in info.get("list") or []:
        prices = sorted(item.get("componentPrices") or [], key=lambda price: price.get("startNumber") or 0)
        image = item.get("minImage") or item.get("componentImageUrl") or ""
        parts.append({
            "lcsc": item.get("componentCode") or "",
            "mpn": item.get("componentModelEn") or "",
            "maker": item.get("componentBrandEn") or "",
            "package": item.get("componentSpecificationEn") or "",
            "category": item.get("firstSortName") or item.get("componentTypeEn") or "",
            "description": re.sub(r"[\ud800-\udfff]", "", item.get("describe") or ""),
            "stock": item.get("stockCount") or 0,
            "price": prices[0].get("productPrice") if prices else None,
            "prices": [(price.get("startNumber"), price.get("productPrice")) for price in prices],
            "basic": item.get("componentLibraryType") == "base",
            "datasheet": item.get("dataManualUrl") or "",
            "url": item.get("lcscGoodsUrl") or "",
            "image": image.replace("/96x96/", "/224x224/") if image
            else FILE.format(item["productBigImageAccessId"]) if item.get("productBigImageAccessId") else "",
        })
    return info.get("total") or 0, parts


def categories():
    """LCSC's categories, as JLCPCB sorts its parts: [(name, count, [(subcategory, count), ...]), ...], by name."""
    answer = _post(SEARCH, {"keyword": "", "currentPage": 1, "pageSize": 1, "searchType": 3})
    found = []
    for sort in ((answer or {}).get("data") or {}).get("sortAndCountVoList") or []:
        children = [(child.get("sortName"), child.get("componentCount") or 0) for child in sort.get("childSortList") or []]
        found.append((sort.get("sortName"), sort.get("componentCount") or 0, sorted(children, key=lambda child: -child[1])))
    return sorted(found, key=lambda each: each[0])


def picture(url, timeout=20):
    """A part's photo, as bytes; None when it cannot be had."""
    if not url:
        return None
    try:
        request = urllib.request.Request(url, headers={"User-Agent": AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except OSError:
        return None


def easyeda(lcsc):
    """Whether EasyEDA has {lcsc}'s symbol, footprint and 3D model, three booleans, and the picture of its symbol: a dict."""
    try:
        result = (_get(EASYEDA.format(lcsc)) or {}).get("result") or {}
    except (OSError, ValueError) as failure:
        raise RuntimeError("EasyEDA did not answer for " + lcsc + " (" + str(failure) + "): it turns away many requests at once; try again in a minute.")
    package = result.get("packageDetail") or {}
    shapes = json.dumps(package.get("dataStr") or {})
    thumb = result.get("thumb") or ""
    return {"symbol": bool(result.get("dataStr")), "footprint": bool(package), "model": "SVGNODE" in shapes,
            "thumb": ("https:" + thumb) if thumb.startswith("//") else thumb}


# ——— Converting ———

def _environment():
    """This process's environment without what KiCad's own Python sets for itself, which would lead another Python astray."""
    return {key: value for key, value in os.environ.items() if key.upper() not in ("PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE", "PYTHONNOUSERSITE", "PYTHONEXECUTABLE")}


def _run(command, timeout):
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace", env=_environment(),
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def converter(settings):
    """A Python that runs easyeda2kicad, or None: the one the settings name, else one found on this computer."""
    candidates = [settings.get("python")] if settings.get("python") else []
    candidates += [shutil.which("python"), shutil.which("python3"), shutil.which("py")]
    if sys.executable and "kicad" not in sys.executable.lower():
        candidates.append(sys.executable)
    for python in candidates:
        if not python:
            continue
        try:
            done = _run([python, "-m", "easyeda2kicad", "--help"], 60)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if done.returncode == 0 and "lcsc_id" in done.stdout:
            return python
    return None


def library_paths(settings):
    folder = Path(settings["library"])
    name = settings["name"]
    return folder, folder / (name + ".kicad_sym"), folder / (name + ".pretty"), folder / (name + ".3dshapes")


def in_library(settings, lcsc):
    """Whether the library already holds the part {lcsc}."""
    if to_server(settings):
        return bool(_server(settings, "GET", "library-has?lcsc=" + urllib.parse.quote(lcsc)).get("kicad"))
    symbols = library_paths(settings)[1]
    try:
        return re.search(r'"LCSC Part"\s+"' + re.escape(lcsc) + '"', symbols.read_text(encoding="utf-8")) is not None
    except OSError:
        return False


def convert(settings, lcsc, overwrite=False):
    """Converts {lcsc} into the library: its symbol, footprint and 3D model. What easyeda2kicad said, as lines."""
    if to_server(settings):
        return [_server(settings, "POST", "library-add", {"lcsc": lcsc}).get("message", "Added " + lcsc + ".")]
    python = converter(settings)
    if python is None:
        raise RuntimeError("easyeda2kicad was not found. Install it with:  python -m pip install easyeda2kicad"
                           "  then name that Python in the settings if it is not on the PATH.")
    folder, symbols, footprints, models = library_paths(settings)
    folder.mkdir(parents=True, exist_ok=True)
    command = [python, "-m", "easyeda2kicad", "--full", "--lcsc_id", lcsc, "--output", str(folder / settings["name"])]
    if overwrite:
        command.append("--overwrite")
    done = _run(command, 300)
    lines = [line.strip() for line in (done.stdout + done.stderr).splitlines() if line.strip() and not line.startswith("--")]
    if done.returncode != 0 or not symbols.exists():
        raise RuntimeError("easyeda2kicad could not convert " + lcsc + ":\n" + "\n".join(lines[-8:]))
    prefer_step(footprints, models)
    return lines


def prefer_step(footprints, models):
    """Each footprint's 3D model as its STEP file where there is one, which KiCad's STEP export needs, not its VRML."""
    if not footprints.is_dir():
        return
    for footprint in footprints.glob("*.kicad_mod"):
        text = footprint.read_text(encoding="utf-8")

        def step(match):
            path = match.group(1)
            candidate = Path(path).with_suffix(".step")
            return '(model "' + str(candidate).replace("\\", "/") + '"' if candidate.exists() else match.group(0)

        changed = re.sub(r'\(model "([^"]+\.wrl)"', step, text)
        if changed != text:
            footprint.write_text(changed, encoding="utf-8")


# ——— KiCad's library tables ———

def kicad_config():
    """KiCad's settings folder, its newest version's: where its global library tables are."""
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "kicad"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Preferences" / "kicad"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "kicad"
    versions = sorted((path for path in base.glob("*") if path.is_dir() and re.fullmatch(r"\d+\.\d+", path.name)),
                      key=lambda path: [int(number) for number in path.name.split(".")])
    return versions[-1] if versions else None


def registered(settings):
    """Whether KiCad's global symbol and footprint tables list the library."""
    if to_server(settings):
        return True  # the server's library goes with each project, in its own tables
    config = kicad_config()
    if config is None:
        return False
    name = '(name "' + settings["name"] + '")'
    return all(name in _read(config / table) for table in ("sym-lib-table", "fp-lib-table"))


def register(settings):
    """Lists the library in KiCad's global symbol and footprint tables, once; what was done, in words."""
    config = kicad_config()
    if config is None:
        raise RuntimeError("KiCad's settings folder was not found: start KiCad once, then try again.")
    _, symbols, footprints, _ = library_paths(settings)
    done = []
    for table, kind, uri in (("sym-lib-table", "sym_lib_table", symbols), ("fp-lib-table", "fp_lib_table", footprints)):
        path = config / table
        text = _read(path) or "(" + kind + "\n  (version 7)\n)\n"
        if '(name "' + settings["name"] + '")' in text:
            continue
        entry = '  (lib (name "{}")(type "KiCad")(uri "{}")(options "")(descr "LCSC parts converted from EasyEDA"))\n'.format(
            settings["name"], str(uri).replace("\\", "/"))
        end = text.rstrip().rfind(")")
        if path.exists():
            shutil.copyfile(path, path.with_name(table + ".before-lcsc"))
        path.write_text(text[:end].rstrip() + "\n" + entry + ")\n", encoding="utf-8")
        done.append(table)
    return ("Added " + settings["name"] + " to KiCad's " + " and ".join(done) + ": restart KiCad, or open Preferences › Manage Libraries,"
            " to see it.") if done else settings["name"] + " is already in KiCad's library tables."


def unregister(settings):
    """Takes the library out of KiCad's global symbol and footprint tables, keeping a copy of each as *.before-retire:
    the server's copy, which each project takes along in its own tables, is then the only one. What was done, in words."""
    config = kicad_config()
    if config is None:
        return "KiCad's settings folder was not found: nothing to take out."
    done = []
    for table in ("sym-lib-table", "fp-lib-table"):
        path = config / table
        text = _read(path)
        kept = [line for line in text.splitlines(True) if '(name "' + settings["name"] + '")' not in line]
        if len(kept) != len(text.splitlines(True)):
            shutil.copyfile(path, path.with_name(table + ".before-retire"))
            path.write_text("".join(kept), encoding="utf-8")
            done.append(table)
    return ("Took " + settings["name"] + " out of KiCad's " + " and ".join(done) + ", keeping copies as *.before-retire.") if done \
        else settings["name"] + " is not in KiCad's global tables."


def _read(path):
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""
