"""The window, laid out as EasyEDA's part selector: LCSC's categories on the left, a search above, and each part a card
with its photo, its package, maker and LCSC number, its datasheet, its prices and stock, what EasyEDA has drawn of it,
and a button that imports it into your KiCad library."""
import io
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor

import wx
import wx.adv
import wx.lib.scrolledpanel as scrolled

from . import core

BACKGROUND = wx.Colour(245, 246, 248)
CARD = wx.Colour(255, 255, 255)
LINE = wx.Colour(227, 230, 235)
LINK = wx.Colour(25, 118, 210)
ORANGE = wx.Colour(255, 106, 0)
GREEN = wx.Colour(46, 125, 50)
MUTED = wx.Colour(110, 116, 125)
PHOTO = 130
PAGE = 20


def scaled(data, size):
    """A photo's bytes as a bitmap fitting a square of {size}, on white, or None."""
    try:
        image = wx.Image(io.BytesIO(data))
    except Exception:  # not a picture wx can read
        return None
    if not image.IsOk():
        return None
    width, height = image.GetWidth(), image.GetHeight()
    ratio = min(size / width, size / height)
    image = image.Scale(max(1, int(width * ratio)), max(1, int(height * ratio)), wx.IMAGE_QUALITY_HIGH)
    image.Resize((size, size), ((size - image.GetWidth()) // 2, (size - image.GetHeight()) // 2), 255, 255, 255)
    return wx.Bitmap(image)


def blank(size):
    bitmap = wx.Bitmap(size, size)
    dc = wx.MemoryDC(bitmap)
    dc.SetBackground(wx.Brush(wx.Colour(238, 240, 243)))
    dc.Clear()
    dc.SetTextForeground(MUTED)
    text = "loading…"
    width, height = dc.GetTextExtent(text)
    dc.DrawText(text, (size - width) // 2, (size - height) // 2)
    dc.SelectObject(wx.NullBitmap)
    return bitmap


def text(parent, label, colour=None, bold=False, size=None):
    control = wx.StaticText(parent, label=label)
    font = control.GetFont()
    if bold:
        font = font.Bold()
    if size:
        font.SetPointSize(size)
    control.SetFont(font)
    if colour is not None:
        control.SetForegroundColour(colour)
    return control


class PartCard(wx.Panel):
    """One part, as EasyEDA's selector shows it."""

    def __init__(self, parent, part, dialog):
        super().__init__(parent)
        self.part = part
        self.dialog = dialog
        self.SetBackgroundColour(CARD)
        self.Bind(wx.EVT_PAINT, self.paint)

        self.photo = wx.StaticBitmap(self, bitmap=blank(PHOTO))
        name = wx.adv.HyperlinkCtrl(self, label=part["mpn"] or part["lcsc"], url=part["url"] or "https://www.lcsc.com")
        font = name.GetFont().Bold()
        font.SetPointSize(font.GetPointSize() + 2)
        name.SetFont(font)
        name.SetNormalColour(LINK)
        name.SetVisitedColour(LINK)

        facts = wx.FlexGridSizer(2, 2, 4, 28)
        facts.Add(self.fact("Footprint: ", part["package"] or "–"))
        facts.Add(self.fact("LCSC Part#: ", part["lcsc"]))
        facts.Add(self.fact("Brand: ", part["maker"] or "–"))
        if part["datasheet"]:
            datasheet = wx.adv.HyperlinkCtrl(self, label="Datasheet (PDF)", url=part["datasheet"])
            datasheet.SetNormalColour(LINK)
            facts.Add(datasheet)
        else:
            facts.Add(text(self, "No datasheet", MUTED))
        description = text(self, part["description"], MUTED)
        description.Wrap(430)
        self.drawn = text(self, "EasyEDA: click the card to see what it has drawn of this part", MUTED)
        self.symbol = wx.StaticBitmap(self, bitmap=wx.Bitmap(1, 1))
        self.symbol.Hide()

        info = wx.BoxSizer(wx.VERTICAL)
        info.Add(name, 0, wx.BOTTOM, 6)
        info.Add(facts, 0, wx.BOTTOM, 6)
        info.Add(description, 0, wx.BOTTOM, 6)
        info.Add(self.drawn)

        prices = wx.FlexGridSizer(0, 2, 3, 6)
        for start, price in part["prices"][:5]:
            prices.Add(text(self, "{}+ :".format(start)), 0, wx.ALIGN_RIGHT)
            prices.Add(text(self, "${:.4f}".format(price or 0), ORANGE))

        right = wx.BoxSizer(wx.VERTICAL)
        stock = wx.BoxSizer(wx.HORIZONTAL)
        stock.Add(text(self, "LCSC Stock: "))
        stock.Add(text(self, format(part["stock"], ","), ORANGE if part["stock"] else MUTED))
        right.Add(stock, 0, wx.BOTTOM, 6)
        kind = text(self, " Basic " if part["basic"] else " Extended ", wx.WHITE, bold=True)
        kind.SetBackgroundColour(GREEN if part["basic"] else wx.Colour(150, 156, 165))
        kind.SetToolTip("Basic parts are loaded on JLCPCB's machines: no setup fee to assemble them." if part["basic"]
                        else "Extended parts are loaded for your order, for a small setup fee.")
        right.Add(kind, 0, wx.BOTTOM, 10)
        right.Add(self.symbol, 0, wx.BOTTOM, 6)
        right.AddStretchSpacer()
        self.action = wx.Button(self, label="Import", size=(120, 32))
        self.action.Bind(wx.EVT_BUTTON, lambda event: dialog.import_parts([part], False))
        right.Add(self.action, 0, wx.ALIGN_RIGHT)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.photo, 0, wx.ALL, 12)
        row.Add(info, 1, wx.TOP | wx.BOTTOM | wx.RIGHT, 12)
        row.Add(prices, 0, wx.TOP | wx.RIGHT, 14)
        row.Add(right, 0, wx.EXPAND | wx.ALL, 12)
        self.SetSizer(row)
        self.Bind(wx.EVT_CONTEXT_MENU, self.menu)
        # What EasyEDA has drawn is asked for one part at a time, when it is looked at: EasyEDA turns away many at once.
        self.checked = False
        for window in [self, self.photo, description, self.drawn]:
            window.Bind(wx.EVT_LEFT_UP, lambda event: self.dialog.check(self))
        self.refresh_state()

    def fact(self, label, value):
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(text(self, label, MUTED))
        row.Add(text(self, value))
        return row

    def paint(self, event):
        dc = wx.PaintDC(self)
        width, height = self.GetClientSize()
        dc.SetPen(wx.Pen(LINE))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(0, 0, width, height)

    def refresh_state(self):
        owned = core.in_library(self.dialog.settings, self.part["lcsc"])
        self.action.SetLabel("✓ In library" if owned else "Import")
        self.action.SetToolTip("Right-click to import it again, replacing it." if owned
                               else "Import its symbol, footprint and 3D model into " + self.dialog.settings["name"])

    def show_drawn(self, drawn):
        marks = [("●" if drawn[key] else "○") + " " + label for key, label in (("symbol", "Symbol"), ("footprint", "Footprint"), ("model", "3D model"))]
        self.drawn.SetLabel("EasyEDA:  " + "   ".join(marks))
        self.drawn.SetForegroundColour(GREEN if all(drawn[key] for key in ("symbol", "footprint")) else ORANGE)
        self.drawn.SetToolTip("What EasyEDA has drawn of this part, which the import converts." if drawn["symbol"]
                              else "EasyEDA has not drawn this part: it cannot be imported.")
        self.Layout()

    def show_symbol(self, bitmap):
        self.symbol.SetBitmap(bitmap)
        self.symbol.SetToolTip("Its symbol, as EasyEDA draws it")
        self.symbol.Show()
        self.Layout()

    def menu(self, event):
        menu = wx.Menu()
        again = menu.Append(wx.ID_ANY, "Import again, replacing it")
        page = menu.Append(wx.ID_ANY, "Open its LCSC page")
        self.Bind(wx.EVT_MENU, lambda _: self.dialog.import_parts([self.part], True), again)
        self.Bind(wx.EVT_MENU, lambda _: webbrowser.open(self.part["url"]) if self.part["url"] else None, page)
        self.PopupMenu(menu)
        menu.Destroy()


class LcscDialog(wx.Dialog):
    def __init__(self, parent=None):
        super().__init__(parent, title="LCSC parts to KiCad", size=(1320, 860), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        self.settings = core.load_settings()
        self.loader = ThreadPoolExecutor(max_workers=6)
        self.pictures = {}
        self.page, self.total = 1, 0
        self.category = self.subcategory = None
        self.generation = 0
        self.SetBackgroundColour(BACKGROUND)

        tab = text(self, "  LCSC Electronics  ", LINK, bold=True)
        tab.SetBackgroundColour(wx.Colour(225, 238, 252))
        self.query = wx.SearchCtrl(self, style=wx.TE_PROCESS_ENTER, size=(-1, 30))
        self.query.SetDescriptiveText("Search, at least 2 characters: a part, a value or an LCSC number (AMS1117-3.3, 10k 0603, C6186)")
        self.query.ShowCancelButton(True)
        self.stocked = wx.CheckBox(self, label="In stock")
        self.stocked.SetValue(True)
        self.basic = wx.CheckBox(self, label="Basic parts only")
        self.sort = wx.Choice(self, choices=list(core.SORTS))
        self.sort.SetSelection(0)
        library = wx.Button(self, label="Library…")

        self.tree = wx.TreeCtrl(self, size=(270, -1), style=wx.TR_HIDE_ROOT | wx.TR_HAS_BUTTONS | wx.TR_LINES_AT_ROOT | wx.TR_SINGLE)
        self.root = self.tree.AddRoot("LCSC")
        self.all = self.tree.AppendItem(self.root, "All parts")
        self.tree.SetItemData(self.all, (None, None))

        self.results = scrolled.ScrolledPanel(self, style=wx.BORDER_NONE)
        self.results.SetBackgroundColour(BACKGROUND)
        self.cards = wx.BoxSizer(wx.VERTICAL)
        self.results.SetSizer(self.cards)
        self.results.SetupScrolling(scroll_x=False, rate_y=24)

        self.first = wx.Button(self, label="|◀", size=(36, -1))
        self.previous = wx.Button(self, label="◀", size=(36, -1))
        self.where = text(self, "")
        self.next = wx.Button(self, label="▶", size=(36, -1))
        self.status = text(self, "", MUTED)
        self.found = text(self, "", bold=True)
        self.found.SetForegroundColour(ORANGE)

        bar = wx.BoxSizer(wx.HORIZONTAL)
        bar.Add(tab, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        bar.Add(self.query, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        for control in (self.stocked, self.basic):
            bar.Add(control, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        bar.Add(text(self, "Sort:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        bar.Add(self.sort, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        bar.Add(library, 0, wx.ALIGN_CENTER_VERTICAL)
        middle = wx.BoxSizer(wx.HORIZONTAL)
        middle.Add(self.tree, 0, wx.EXPAND | wx.RIGHT, 8)
        middle.Add(self.results, 1, wx.EXPAND)
        pager = wx.BoxSizer(wx.HORIZONTAL)
        pager.Add(self.status, 1, wx.ALIGN_CENTER_VERTICAL)
        for control in (self.first, self.previous):
            pager.Add(control, 0, wx.RIGHT, 4)
        pager.Add(self.where, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 8)
        pager.Add(self.next, 0, wx.RIGHT, 12)
        pager.Add(text(self, "Filter result: "), 0, wx.ALIGN_CENTER_VERTICAL)
        pager.Add(self.found, 0, wx.ALIGN_CENTER_VERTICAL)
        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(bar, 0, wx.EXPAND | wx.ALL, 10)
        box.Add(middle, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        box.Add(pager, 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(box)

        self.query.Bind(wx.EVT_TEXT_ENTER, lambda event: self.find(1))
        self.query.Bind(wx.EVT_SEARCHCTRL_SEARCH_BTN, lambda event: self.find(1))
        self.query.Bind(wx.EVT_SEARCHCTRL_CANCEL_BTN, lambda event: (self.query.SetValue(""), self.find(1)))
        for control in (self.stocked, self.basic):
            control.Bind(wx.EVT_CHECKBOX, lambda event: self.find(1))
        self.sort.Bind(wx.EVT_CHOICE, lambda event: self.find(1))
        self.tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.chose_category)
        self.first.Bind(wx.EVT_BUTTON, lambda event: self.find(1))
        self.previous.Bind(wx.EVT_BUTTON, lambda event: self.find(self.page - 1))
        self.next.Bind(wx.EVT_BUTTON, lambda event: self.find(self.page + 1))
        library.Bind(wx.EVT_BUTTON, lambda event: self.choose_library())
        self.Bind(wx.EVT_CLOSE, self.closing)
        self.show_library()
        self.work(core.categories, self.show_categories)

    # ——— Categories ———

    def show_categories(self, categories):
        for name, count, children in categories:
            item = self.tree.AppendItem(self.root, "{}  ({:,})".format(name, count))
            self.tree.SetItemData(item, (name, None))
            for child, number in children:
                self.tree.SetItemData(self.tree.AppendItem(item, "{}  ({:,})".format(child, number)), (name, child))

    def chose_category(self, event):
        if not self or self.IsBeingDeleted():
            return
        data = self.tree.GetItemData(event.GetItem()) if event.GetItem().IsOk() else None
        if data is None:
            return
        self.category, self.subcategory = data
        self.find(1)

    # ——— Searching ———

    def find(self, page):
        keyword = self.query.GetValue().strip()
        if len(keyword) == 1:
            self.say("Type at least 2 characters.")
            return
        if not keyword and not self.category:
            self.say("Search for a part, or choose a category on the left.")
            return
        self.page = max(1, page)
        self.generation += 1
        generation = self.generation
        where = self.subcategory or self.category
        self.say("Searching LCSC" + (" for " + keyword if keyword else "") + (" in " + where if where else "") + "…")
        options = dict(page=self.page, size=PAGE, category=self.category, subcategory=self.subcategory, basic=self.basic.GetValue(),
                       in_stock=self.stocked.GetValue(), sort=self.sort.GetStringSelection())
        self.work(lambda: core.search(keyword, **options), lambda answer: self.show(answer, generation))

    def show(self, answer, generation):
        if generation != self.generation:
            return
        self.total, parts = answer
        self.results.Freeze()
        self.cards.Clear(delete_windows=True)
        for part in parts:
            card = PartCard(self.results, part, self)
            self.cards.Add(card, 0, wx.EXPAND | wx.BOTTOM, 10)
            self.load(card, generation)
        self.results.SetupScrolling(scroll_x=False, rate_y=24, scrollToTop=True)
        self.results.Thaw()
        pages = max(1, -(-self.total // PAGE))
        self.where.SetLabel("Page {} of {:,}".format(self.page, pages))
        self.found.SetLabel("{:,}".format(self.total))
        self.first.Enable(self.page > 1)
        self.previous.Enable(self.page > 1)
        self.next.Enable(self.page < pages)
        self.say("{:,} parts. Import one to have its symbol, footprint and 3D model in {}.".format(self.total, self.settings["name"])
                 if parts else "Nothing found: try fewer words, or untick In stock.")
        self.Layout()

    def load(self, card, generation):
        """Fills {card} in with its photo once it arrives."""
        part = card.part

        def fetch():
            photo = self.pictures.get(part["image"]) or core.picture(part["image"])
            self.pictures[part["image"]] = photo
            wx.CallAfter(self.shown, card, generation, lambda: card.photo.SetBitmap(scaled(photo, PHOTO) or blank(PHOTO)) if photo else None)
        self.loader.submit(fetch)

    def check(self, card):
        """Asks EasyEDA what it has drawn of {card}'s part, once, and shows it, with its symbol's picture."""
        if card.checked:
            return
        card.checked = True
        card.drawn.SetLabel("EasyEDA: looking…")
        generation = self.generation

        def fetch():
            try:
                drawn = core.easyeda(card.part["lcsc"])
            except RuntimeError as failure:
                def again():
                    card.checked = False
                    card.drawn.SetLabel("EasyEDA did not answer: click to try again")
                    card.drawn.SetForegroundColour(ORANGE)
                    self.say(str(failure))
                wx.CallAfter(self.shown, card, generation, again)
                return
            wx.CallAfter(self.shown, card, generation, lambda: card.show_drawn(drawn))
            symbol = core.picture(drawn.get("thumb"))
            bitmap = scaled(symbol, 70) if symbol else None
            if bitmap:
                wx.CallAfter(self.shown, card, generation, lambda: card.show_symbol(bitmap))
        threading.Thread(target=fetch, daemon=True).start()

    def shown(self, card, generation, change):
        if generation != self.generation:
            return
        try:
            change()
            self.results.Layout()
        except RuntimeError:  # the card was already taken away by a newer search
            pass

    # ——— Importing ———

    def import_parts(self, parts, overwrite):
        settings = dict(self.settings)

        def run():
            lines = []
            for part in parts:
                if core.in_library(settings, part["lcsc"]) and not overwrite:
                    lines.append(part["lcsc"] + " is already in " + settings["name"] + ": right-click it to import it again.")
                    continue
                core.convert(settings, part["lcsc"], overwrite)
                lines.append("Imported {} {} into {}: its symbol, footprint and 3D model. In KiCad: Place › Add Symbol, library {}."
                             .format(part["lcsc"], part["mpn"], settings["name"], settings["name"]))
            if not core.registered(settings):
                lines.append(core.register(settings))
            return lines

        self.say("Converting " + ", ".join(part["lcsc"] for part in parts) + " with easyeda2kicad…")
        self.work(run, self.imported)

    def imported(self, lines):
        self.say("  ".join(lines))
        for child in self.cards.GetChildren():
            if isinstance(child.GetWindow(), PartCard):
                child.GetWindow().refresh_state()

    def choose_library(self):
        link = wx.GetTextFromUser("The desktop link from Product Architecture Studio's page (Connect a desktop program…): parts then go into "
                                  "the server's LCSC library, which every project written from it takes along. Leave it empty for a library "
                                  "on this computer.", "Where parts go", self.settings.get("server", ""), self)
        self.settings["server"] = link.strip()
        if core.to_server(self.settings):
            core.save_settings(self.settings)
            self.show_library()
            return
        with wx.DirDialog(self, "The folder of your LCSC library", self.settings["library"]) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            self.settings["library"] = dialog.GetPath()
        name = wx.GetTextFromUser("Its name in KiCad's library tables:", "Library name", self.settings["name"], self)
        if name.strip():
            self.settings["name"] = name.strip()
        core.save_settings(self.settings)
        self.show_library()

    def show_library(self):
        if core.to_server(self.settings):
            self.say("Library: the server's LCSC library, through " + self.settings["server"].split("/api/")[0] + ": each part converted there.")
            return
        self.say("Library: " + self.settings["name"] + " in " + self.settings["library"]
                 + ("" if core.registered(self.settings) else " (added to KiCad's tables on the first import)"))

    # ——— Helpers ———

    def say(self, line):
        self.status.SetLabel(line)
        self.status.SetToolTip(line)

    def work(self, task, done):
        """Runs {task} away from the window, then {done} with its answer in it; a failure is said below."""
        def run():
            try:
                answer = task()
            except Exception as failure:  # the status line says what went wrong, whatever it was
                wx.CallAfter(self.say, "Failed: " + str(failure))
                return
            wx.CallAfter(done, answer)
        threading.Thread(target=run, daemon=True).start()

    def closing(self, event):
        self.generation += 1
        self.loader.shutdown(wait=False, cancel_futures=True)
        event.Skip()
