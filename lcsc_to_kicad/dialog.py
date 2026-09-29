"""The window: search LCSC's parts, see which EasyEDA has drawn, and import those chosen into your KiCad library."""
import threading
import webbrowser

import wx

from . import core

COLUMNS = (("LCSC", 80), ("Part", 170), ("Maker", 140), ("Package", 120), ("Stock", 80), ("Price $", 60), ("Kind", 65), ("In library", 75))


class LcscDialog(wx.Dialog):
    def __init__(self, parent=None):
        super().__init__(parent, title="LCSC parts to KiCad", size=(980, 680), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.settings = core.load_settings()
        self.parts = []
        self.page = 1
        self.total = 0
        self.keyword = ""

        self.query = wx.SearchCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.query.SetDescriptiveText("A part, a value or an LCSC number: AMS1117-3.3, 10k 0603, C6186…")
        self.query.ShowCancelButton(True)
        self.basic = wx.CheckBox(self, label="Basic parts only")
        find = wx.Button(self, label="Search")
        self.results = wx.ListCtrl(self, style=wx.LC_REPORT)
        for index, (title, width) in enumerate(COLUMNS):
            self.results.InsertColumn(index, title, width=width)
        self.more = wx.Button(self, label="More results")
        self.more.Disable()
        self.count = wx.StaticText(self, label="")
        self.details = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 90))
        datasheet = wx.Button(self, label="Datasheet")
        page = wx.Button(self, label="LCSC page")
        self.overwrite = wx.CheckBox(self, label="Replace parts already in the library")
        self.importer = wx.Button(self, label="Import selected into " + self.settings["name"])
        self.library = wx.StaticText(self, label="")
        change = wx.Button(self, label="Library…")
        self.log = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 110))

        top = wx.BoxSizer(wx.HORIZONTAL)
        top.Add(self.query, 1, wx.EXPAND | wx.RIGHT, 6)
        top.Add(self.basic, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        top.Add(find)
        paging = wx.BoxSizer(wx.HORIZONTAL)
        paging.Add(self.count, 1, wx.ALIGN_CENTER_VERTICAL)
        paging.Add(self.more)
        links = wx.BoxSizer(wx.HORIZONTAL)
        links.Add(datasheet, 0, wx.RIGHT, 6)
        links.Add(page)
        links.AddStretchSpacer()
        links.Add(self.overwrite, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        links.Add(self.importer)
        where = wx.BoxSizer(wx.HORIZONTAL)
        where.Add(self.library, 1, wx.ALIGN_CENTER_VERTICAL)
        where.Add(change)
        box = wx.BoxSizer(wx.VERTICAL)
        for item, proportion in ((top, 0), (self.results, 3), (paging, 0), (self.details, 0), (links, 0), (where, 0), (self.log, 1)):
            box.Add(item, proportion, wx.EXPAND | wx.ALL, 6)
        self.SetSizer(box)

        self.query.Bind(wx.EVT_TEXT_ENTER, lambda event: self.find())
        self.query.Bind(wx.EVT_SEARCHCTRL_SEARCH_BTN, lambda event: self.find())
        find.Bind(wx.EVT_BUTTON, lambda event: self.find())
        self.more.Bind(wx.EVT_BUTTON, lambda event: self.find(self.page + 1))
        self.results.Bind(wx.EVT_LIST_ITEM_SELECTED, self.selected)
        self.results.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda event: self.import_selected())
        datasheet.Bind(wx.EVT_BUTTON, lambda event: self.open_link("datasheet"))
        page.Bind(wx.EVT_BUTTON, lambda event: self.open_link("url"))
        self.importer.Bind(wx.EVT_BUTTON, lambda event: self.import_selected())
        change.Bind(wx.EVT_BUTTON, lambda event: self.choose_library())
        self.show_library()

    # ——— Searching ———

    def find(self, page=1):
        keyword = self.query.GetValue().strip()
        if not keyword:
            return
        self.keyword, self.page = keyword, page
        self.say("Searching LCSC for " + keyword + "…")
        self.work(lambda: core.search(keyword, page), self.found)

    def found(self, answer):
        total, parts = answer
        if self.basic.GetValue():
            parts = [part for part in parts if part["basic"]]
        if self.page == 1:
            self.parts = []
            self.results.DeleteAllItems()
        for part in parts:
            row = self.results.InsertItem(self.results.GetItemCount(), part["lcsc"])
            values = (part["mpn"], part["maker"], part["package"], format(part["stock"], ","),
                      "" if part["price"] is None else "%.4f" % part["price"], "Basic" if part["basic"] else "Extended",
                      "yes" if core.in_library(self.settings, part["lcsc"]) else "")
            for column, value in enumerate(values, 1):
                self.results.SetItem(row, column, value)
            self.parts.append(part)
        self.total = total
        self.count.SetLabel("{} of {} parts".format(len(self.parts), total))
        self.more.Enable(self.page * 30 < total)
        self.say("Found {} parts for {}. Select one to see whether EasyEDA has drawn it; double-click, or Import, to add it.".format(total, self.keyword))

    def selected(self, event):
        part = self.parts[event.GetIndex()]
        text = "{lcsc}  {mpn}  ({maker})\n{category} · {package}\n{description}".format(**part)
        self.details.SetValue(text + "\nEasyEDA: looking…")
        self.work(lambda: core.easyeda(part["lcsc"]), lambda drawn: self.details.SetValue(text + "\nEasyEDA: " + ", ".join(
            ("✓ " if drawn[key] else "✗ no ") + label for key, label in (("symbol", "symbol"), ("footprint", "footprint"), ("model", "3D model")))))

    def chosen(self):
        rows, row = [], self.results.GetFirstSelected()
        while row != -1:
            rows.append(self.parts[row])
            row = self.results.GetNextSelected(row)
        return rows

    def open_link(self, key):
        for part in self.chosen()[:1]:
            if part[key]:
                webbrowser.open(part[key])

    # ——— Importing ———

    def import_selected(self):
        parts = self.chosen()
        if not parts:
            self.say("Select one part or more first.")
            return
        overwrite = self.overwrite.GetValue()
        settings = dict(self.settings)

        def run():
            lines = []
            for part in parts:
                if core.in_library(settings, part["lcsc"]) and not overwrite:
                    lines.append(part["lcsc"] + " is already in " + settings["name"] + ": tick Replace to convert it again.")
                    continue
                core.convert(settings, part["lcsc"], overwrite)
                lines.append("Imported " + part["lcsc"] + " " + part["mpn"] + " into " + settings["name"] + ": its symbol, footprint and 3D model.")
            if not core.registered(settings):
                lines.append(core.register(settings))
            return lines

        self.say("Converting " + ", ".join(part["lcsc"] for part in parts) + " with easyeda2kicad…")
        self.work(run, self.imported)

    def imported(self, lines):
        for line in lines:
            self.say(line)
        for row, part in enumerate(self.parts):
            self.results.SetItem(row, 7, "yes" if core.in_library(self.settings, part["lcsc"]) else "")
        self.say("In KiCad: Place › Add Symbol, library " + self.settings["name"] + "; each symbol has its footprint and LCSC number set.")

    def choose_library(self):
        with wx.DirDialog(self, "The folder of your LCSC library", self.settings["library"]) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            self.settings["library"] = dialog.GetPath()
        name = wx.GetTextFromUser("Its name in KiCad's library tables:", "Library name", self.settings["name"], self)
        if name.strip():
            self.settings["name"] = name.strip()
        core.save_settings(self.settings)
        self.importer.SetLabel("Import selected into " + self.settings["name"])
        self.show_library()

    def show_library(self):
        self.library.SetLabel("Library: " + self.settings["name"] + " in " + self.settings["library"]
                              + ("" if core.registered(self.settings) else "  (added to KiCad's tables on the first import)"))

    # ——— Helpers ———

    def say(self, line):
        self.log.AppendText(line + "\n")

    def work(self, task, done):
        """Runs {task} away from the window, then {done} with its answer in it; a failure is said in the log."""
        def run():
            try:
                answer = task()
            except Exception as failure:  # the log says what went wrong, whatever it was
                wx.CallAfter(self.say, "Failed: " + str(failure))
                return
            wx.CallAfter(done, answer)
        threading.Thread(target=run, daemon=True).start()
