"""LCSC parts to a KiCad library: search JLCPCB's parts, and convert a part's EasyEDA symbol, footprint and 3D model into
one library of your own, which KiCad's Schematic and PCB editors then both find.

The search asks JLCPCB's parts search, as its website does; the conversion is easyeda2kicad's (AGPL-3.0), run with a
Python that has it installed (pip install easyeda2kicad). Each part converted is checked, as Modular Electronics Studio
checks its own library, and LCSC's record of it written into its symbol. Nothing here needs KiCad's own Python but the
window and placing a part on a board (place.py).
"""
import datetime
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
        # The desktop link Modular Electronics Studio's page gives (Connect a desktop program…): parts then go into the
        # server's LCSC library, the one copy, which every KiCad project written from it takes along.
        "server": "",
    }


def to_server(settings):
    """Whether parts go to Modular Electronics Studio's server, rather than into a library on this computer."""
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
    try:
        describe(settings, lcsc)
    except (OSError, ValueError) as failure:
        lines.append("No record of " + lcsc + " from LCSC: " + str(failure))
    return lines + check(folder, settings["name"], {lcsc})


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


def describe(settings, lcsc):
    """Writes LCSC's record of {lcsc} into its symbol, as hidden fields: Manufacturer, MPN, Description and, where it has
    none, Datasheet; and the record, with its price breaks and stock, into records.json beside the library. The record,
    or None when LCSC has none."""
    found = next((part for part in search(lcsc, size=10)[1] if part["lcsc"].upper() == lcsc.upper()), None)
    if found is None:
        return None
    folder, symbols, _, _ = library_paths(settings)
    text = _read(symbols)
    for start, end in reversed(blocks(text, "symbol")):
        block = text[start:end]
        if number_of(block).upper() != lcsc.upper():
            continue
        for field, value in (("Manufacturer", found["maker"]), ("MPN", found["mpn"]), ("Description", found["description"])):
            block = set_prop(block, field, value)
        if not prop(block, "Datasheet"):
            block = set_prop(block, "Datasheet", found["datasheet"])
        text = text[:start] + block + text[end:]
    _write(symbols, text)
    records = folder / "records.json"
    try:
        kept = json.loads(_read(records) or "{}")
    except ValueError:
        kept = {}
    kept[lcsc.upper()] = dict(found, checked=datetime.date.today().isoformat())
    _write(records, json.dumps(dict(sorted(kept.items())), indent=1, ensure_ascii=False) + "\n")
    return found


# ——— A library's symbols, as KiCad writes them: only as far as finding them and reading their fields ———

def blocks(text, head):
    """The spans (start, end) of each block directly inside the outermost one whose head is {head}, as (symbol "…" …)."""
    spans, depth, start, index, inside = [], 0, None, 0, False
    while index < len(text):
        character = text[index]
        if inside:
            if character == "\\":
                index += 1
            elif character == '"':
                inside = False
        elif character == '"':
            inside = True
        elif character == "(":
            depth += 1
            if depth == 2 and re.match(r"\(\s*" + re.escape(head) + r"[\s)]", text[index:index + len(head) + 3]):
                start = index
        elif character == ")":
            if depth == 2 and start is not None:
                spans.append((start, index + 1))
                start = None
            depth -= 1
        index += 1
    return spans


def first_string(block):
    """The block's first quoted atom, such as a symbol's name."""
    found = re.match(r'\(\s*\w+\s+"((?:[^"\\]|\\.)*)"', block)
    return found.group(1) if found else ""


def prop(block, name):
    """A symbol's property {name}, or ''."""
    found = re.search(r'\(property\s+"' + re.escape(name) + r'"\s+"((?:[^"\\]|\\.)*)"', block)
    value = found.group(1) if found else ""
    return "" if value == "~" else value


def number_of(block):
    """A symbol's LCSC number, as easyeda2kicad names it (LCSC Part) or as others do (LCSC); '' when it has none."""
    return prop(block, "LCSC Part") or prop(block, "LCSC")


def _quote(text):
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def set_prop(block, name, value):
    """{block}, a symbol, with its property {name} set to {value}: changed where it has it, else added after its last
    property, hidden."""
    if not value:
        return block
    pattern = re.compile(r'(\(property\s+"' + re.escape(name) + r'"\s+)"(?:[^"\\]|\\.)*"')
    if pattern.search(block):
        return pattern.sub(lambda match: match.group(1) + _quote(value), block, count=1)
    last = None
    for found in re.finditer(r"\(property\s", block):
        last = found
    if last is None:
        return block
    # The end of the last property: its parentheses closed.
    depth, index, inside = 0, last.start(), False
    while index < len(block):
        character = block[index]
        if inside:
            if character == "\\":
                index += 1
            elif character == '"':
                inside = False
        elif character == '"':
            inside = True
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                break
        index += 1
    indent = re.search(r"\n([ \t]*)\(property", block)
    lead = "\n" + (indent.group(1) if indent else "    ")
    added = lead + "(property " + _quote(name) + " " + _quote(value) + " (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))"
    return block[:index + 1] + added + block[index + 1:]


def pins(block):
    """The numbers of a symbol's pins, its units' together."""
    return re.findall(r'\(pin\s+\w+\s+\w+.*?\(number\s+"((?:[^"\\]|\\.)*)"', block, flags=re.S)


def symbol(text, lcsc):
    """The symbol in {text}, a .kicad_sym, whose LCSC number is {lcsc}; None when it has none."""
    for start, end in blocks(text, "symbol"):
        if number_of(text[start:end]).upper() == lcsc.upper():
            return text[start:end]
    return None


# ——— The check ———

def check(folder, name, only=None):
    """Where the library {name} in {folder} disagrees with itself, one line a finding, PROBLEM or NOTE, the part named:
    every symbol has an LCSC number and a footprint in the library, every pin a pad of its number on it, a pad no pin
    names is said (a shield, a mounting hole), and every 3D model a footprint names is there. Only the parts whose LCSC
    numbers are in {only}, when given."""
    folder, lines = Path(folder), []
    text = _read(folder / (name + ".kicad_sym"))
    for start, end in blocks(text, "symbol"):
        block = text[start:end]
        number = number_of(block)
        if only is not None and number.upper() not in {each.upper() for each in only}:
            continue
        part = (number + " " if number else "") + first_string(block)
        if not number:
            lines.append("PROBLEM " + part + ": its symbol has no LCSC Part field.")
        footprint = prop(block, "Footprint")
        own = footprint.split(":", 1)[-1]
        path = folder / (name + ".pretty") / (own + ".kicad_mod")
        if not own or not path.is_file():
            lines.append("PROBLEM " + part + ": its footprint " + (footprint + " is not in the library" if own else "is not named") + ".")
            continue
        board = _read(path)
        # A pad's number quoted, (pad "1" …), or bare, (pad 1 …), as newer footprints write it.
        pads = {quoted or bare for quoted, bare in re.findall(r'\(pad\s+(?:"((?:[^"\\]|\\.)*)"|([^\s()"]+))', board)}
        numbers = pins(block)
        unpadded = sorted({each for each in numbers if each not in pads})
        if unpadded:
            lines.append("PROBLEM " + part + ": pins " + ", ".join(unpadded) + " have no pad on " + footprint + ".")
        unpinned = sorted(each for each in pads if each and each not in set(numbers))
        if unpinned:
            lines.append("NOTE " + part + ": pads " + ", ".join(unpinned) + " of " + footprint + " are no pin's, such as a shield or a mounting hole.")
        for model in re.findall(r'\(model "([^"]+)"', board):
            if not (folder / (name + ".3dshapes") / model.replace("\\", "/").split("/")[-1]).is_file():
                lines.append("PROBLEM " + part + ": its 3D model " + model + " is not in " + name + ".3dshapes.")
    return lines


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


def use(settings, folder):
    """Tells KiCad where Modular Electronics Studio's LCSC library is, {folder}, its `library/lcsc/kicad` on the computer the
    server runs on: the path variable LCSC_LIBRARY, by which its footprints name their 3D models, and LCSC in KiCad's global
    symbol and footprint tables, in place of any LCSC there, each file kept as *.before-use. What was done, in words."""
    folder = Path(folder).resolve()
    name = settings["name"]
    if not (folder / (name + ".kicad_sym")).is_file() or not (folder / (name + ".pretty")).is_dir():
        raise RuntimeError(str(folder) + " holds no " + name + ".kicad_sym and " + name + ".pretty.")
    config = kicad_config()
    if config is None:
        raise RuntimeError("KiCad's settings folder was not found: start KiCad once, then try again.")
    variable = name + "_LIBRARY"
    common = config / "kicad_common.json"
    try:
        data = json.loads(_read(common) or "{}")
    except ValueError:
        raise RuntimeError(str(common) + " cannot be read, and is left as it is.")
    if common.exists():
        shutil.copyfile(common, common.with_name("kicad_common.json.before-use"))
    variables = data.setdefault("environment", {}).get("vars") or {}
    variables[variable] = str(folder)
    data["environment"]["vars"] = variables
    common.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    for table, kind, uri in (("sym-lib-table", "sym_lib_table", name + ".kicad_sym"), ("fp-lib-table", "fp_lib_table", name + ".pretty")):
        path = config / table
        text = _read(path) or "(" + kind + "\n  (version 7)\n)\n"
        if path.exists():
            shutil.copyfile(path, path.with_name(table + ".before-use"))
        kept = "".join(line for line in text.splitlines(True) if '(name "' + name + '")' not in line)
        entry = '  (lib (name "{}")(type "KiCad")(uri "${{{}}}/{}")(options "")(descr "Parts from LCSC, Modular Electronics Studio\'s library"))\n'.format(
            name, variable, uri)
        end = kept.rstrip().rfind(")")
        path.write_text(kept[:end].rstrip() + "\n" + entry + ")\n", encoding="utf-8")
    return ("KiCad now finds " + name + " in " + str(folder) + ": " + variable + " is set, and " + name + " is in its global symbol and"
            " footprint tables (the files before kept as *.before-use). Restart KiCad to see it.")


def add_to_project(folder, name, project):
    """Lists the library {name} in {folder} in the KiCad project in {project}, its own symbol and footprint tables, by its
    path from the project, so that the project finds it wherever it is opened beside it. What was done, in words."""
    project = Path(project)
    project.mkdir(parents=True, exist_ok=True)
    where = os.path.relpath(str(Path(folder).resolve()), str(project.resolve())).replace("\\", "/")
    done = []
    for table, kind, entry in (("sym-lib-table", "sym_lib_table", name + ".kicad_sym"), ("fp-lib-table", "fp_lib_table", name + ".pretty")):
        path = project / table
        text = _read(path) or "(" + kind + "\n  (version 7)\n)\n"
        if re.search(r'\(lib\s+\(name\s+"?' + re.escape(name) + r'"?\)', text):
            continue
        line = '  (lib (name "{}")(type "KiCad")(uri "${{KIPRJMOD}}/{}/{}")(options "")(descr "LCSC parts converted from EasyEDA"))\n'.format(
            name, where, entry)
        end = text.rstrip().rfind(")")
        _write(path, text[:end].rstrip() + "\n" + line + ")\n")
        done.append(table)
    return ("Added " + name + " to the project's " + " and ".join(done) + ".") if done else name + " is already in the project's library tables."


# ——— Where KiCad finds a part's footprint ———

def footprint_libraries(project):
    """The footprint libraries KiCad finds for a board in {project}: {nickname: its .pretty folder}, the project's own
    table before KiCad's global one, each path with its variables filled in, from the project's folder (KIPRJMOD),
    KiCad's settings and the environment."""
    config = kicad_config()
    variables = dict(os.environ)
    if config is not None:
        try:
            variables.update(((json.loads(_read(config / "kicad_common.json") or "{}").get("environment") or {}).get("vars")) or {})
        except ValueError:
            pass
    variables["KIPRJMOD"] = str(project or "")
    found = {}
    for table in (([Path(project) / "fp-lib-table"] if project else []) + ([config / "fp-lib-table"] if config is not None else [])):
        for nickname, uri in re.findall(r'\(lib\s+\(name\s+"?([^")]+)"?\)\s*\(type\s+"?[^")]+"?\)\s*\(uri\s+"?([^")]+)"?\)', _read(table)):
            path = re.sub(r"\$\{(\w+)\}", lambda match: variables.get(match.group(1), match.group(0)), uri)
            found.setdefault(nickname, Path(path))
    return found


def footprint_of(settings, lcsc, project):
    """Where the part {lcsc} is for a board in {project}, as a dict: its footprint library's nickname and folder, its
    footprint's name, the letters of its reference, its value and its record's fields; from the library of the settings'
    name that KiCad finds for the board, else the library on this computer. Raises when neither holds it."""
    name = settings["name"]
    folders = [footprint_libraries(project).get(name)]
    if not to_server(settings):
        folders.append(library_paths(settings)[2])
    for pretty in (folder for folder in folders if folder is not None):
        block = symbol(_read(pretty.with_suffix(".kicad_sym")), lcsc)
        if block is None:
            continue
        footprint = prop(block, "Footprint").split(":", 1)[-1]
        if footprint and (pretty / (footprint + ".kicad_mod")).is_file():
            return {"library": name, "folder": str(pretty), "footprint": footprint,
                    "reference": re.sub(r"[^A-Za-z]", "", prop(block, "Reference")) or "U", "value": prop(block, "Value") or lcsc,
                    "fields": {field: prop(block, key) for field, key in (("LCSC", "LCSC Part"), ("Manufacturer", "Manufacturer"), ("MPN", "MPN"))
                               if prop(block, key)}}
    raise RuntimeError(lcsc + " is in no " + name + " library KiCad finds for this board: import it first"
                       + (", and run run.py --use with the server's library/lcsc/kicad" if to_server(settings) else "") + ".")


def symbol_of(settings, lcsc, project=None):
    """The symbol of the part {lcsc}, as (its block in its .kicad_sym, that file's format version), from the library of
    the settings' name that KiCad finds for {project} (or KiCad's global tables, without one), else the library on this
    computer. Raises when neither holds it."""
    name = settings["name"]
    folders = [footprint_libraries(project).get(name)]
    if not to_server(settings):
        folders.append(library_paths(settings)[2])
    for pretty in (folder for folder in folders if folder is not None):
        text = _read(pretty.with_suffix(".kicad_sym"))
        block = symbol(text, lcsc)
        if block is not None:
            version = re.search(r"\(version\s+(\d+)\)", text)
            return block, version.group(1) if version else "20211014"
    raise RuntimeError(lcsc + " is in no " + name + " library KiCad finds: import it first"
                       + (", and run run.py --use with the server's library/lcsc/kicad" if to_server(settings) else "") + ".")


def _read(path):
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _write(path, text):
    """Writes {text} as UTF-8 with Unix line endings, as KiCad writes its files."""
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        file.write(text)
