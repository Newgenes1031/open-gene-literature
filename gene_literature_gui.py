"""Small native Windows/macOS interface for Open Gene Literature."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import shutil
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from gene_literature import VERSION, save_report, search_literature

SORTS = {"관련도순": "relevance", "최신순": "recent", "인용순": "cited"}


def user_cache_dir():
    """Never store writable data inside a bundled app or its temporary files."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return base / "OpenGeneLiterature"


def validate_search(gene, count, sort):
    if not gene.strip():
        raise ValueError("유전자명을 입력하세요. 예: FASN, TP53, STAT3")
    try:
        limit = int(count)
    except (TypeError, ValueError):
        raise ValueError("논문 수는 1~300 사이의 정수로 입력하세요.") from None
    if not 1 <= limit <= 300:
        raise ValueError("논문 수는 1~300 사이로 입력하세요.")
    if sort not in SORTS:
        raise ValueError("정렬 방식을 선택하세요.")
    return gene.strip(), limit, SORTS[sort]


class LiteratureApp(ttk.Frame):
    def __init__(self, root):
        super().__init__(root, padding=16)
        self.root = root
        self.pack(fill="both", expand=True)
        root.title(f"Open Gene Literature {VERSION}")
        root.geometry("1080x740")
        root.minsize(840, 620)
        self.gene = tk.StringVar()
        self.context = tk.StringVar()
        self.count = tk.StringVar(value="30")
        self.sort = tk.StringVar(value="관련도순")
        self.aliases = tk.BooleanVar(value=False)
        self.output = tk.StringVar(value=str(Path.home() / "Documents" / "OpenGeneLiterature"))
        self.status = tk.StringVar(value="유전자명을 입력하고 검색을 누르세요. 사람 유전자 기준입니다.")
        self.events = queue.Queue()
        self.report = None
        self.report_dir = None
        self.busy = False
        self._build()
        root.bind("<Return>", lambda event: self.start_search())
        self.after(100, self._poll)

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=3)
        self.rowconfigure(4, weight=2)
        form = ttk.LabelFrame(self, text="논문 검색", padding=12)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(3, weight=1)
        ttk.Label(form, text="유전자명").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.gene_entry = ttk.Entry(form, textvariable=self.gene, width=18)
        self.gene_entry.grid(row=0, column=1, sticky="ew", padx=(0, 16))
        self.gene_entry.focus_set()
        ttk.Label(form, text="관심 주제 (선택)").grid(row=0, column=2, sticky="w", padx=(0, 8))
        ttk.Entry(form, textvariable=self.context).grid(row=0, column=3, sticky="ew")
        ttk.Label(form, text="예: FASN / TP53 / p53", foreground="#5b6570").grid(row=1, column=1, sticky="w")
        ttk.Label(form, text='예: cancer 또는 "colorectal cancer" (따옴표 없이 입력)', foreground="#5b6570").grid(row=1, column=3, sticky="w")
        options = ttk.Frame(form)
        options.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        ttk.Label(options, text="정렬").pack(side="left")
        ttk.Combobox(options, textvariable=self.sort, values=list(SORTS), state="readonly", width=10).pack(side="left", padx=(8, 18))
        ttk.Label(options, text="논문 수").pack(side="left")
        ttk.Spinbox(options, from_=1, to=300, textvariable=self.count, width=6).pack(side="left", padx=(8, 18))
        ttk.Checkbutton(options, text="다른 별칭도 포함", variable=self.aliases).pack(side="left")
        self.search_button = ttk.Button(options, text="검색", command=self.start_search)
        self.search_button.pack(side="right")
        folder = ttk.Frame(self)
        folder.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        folder.columnconfigure(1, weight=1)
        ttk.Label(folder, text="저장 폴더").grid(row=0, column=0, padx=(0, 8))
        ttk.Entry(folder, textvariable=self.output).grid(row=0, column=1, sticky="ew")
        ttk.Button(folder, text="변경…", command=self.choose_folder).grid(row=0, column=2, padx=(8, 0))
        toolbar = ttk.Frame(self)
        toolbar.grid(row=2, column=0, sticky="ew", pady=10)
        self.spinner = ttk.Progressbar(toolbar, mode="indeterminate", length=65)
        self.spinner.pack(side="left", padx=(0, 10))
        ttk.Label(toolbar, textvariable=self.status, wraplength=650).pack(side="left", fill="x", expand=True)
        self.report_button = ttk.Button(toolbar, text="보고서 열기", command=self.open_report, state="disabled")
        self.report_button.pack(side="right")
        self.csv_button = ttk.Button(toolbar, text="CSV 내보내기", command=self.export_csv, state="disabled")
        self.csv_button.pack(side="right", padx=(0, 8))
        results = ttk.Frame(self)
        results.grid(row=3, column=0, sticky="nsew")
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)
        self.table = ttk.Treeview(results, columns=("year", "journal", "kind", "citations"), selectmode="browse")
        self.table.heading("#0", text="논문 제목")
        self.table.column("#0", width=470, minwidth=220)
        for key, label, width in [("year", "연도", 60), ("journal", "저널", 180),
                                  ("kind", "종류", 90), ("citations", "인용 수", 65)]:
            self.table.heading(key, text=label)
            self.table.column(key, width=width, minwidth=50, stretch=(key == "journal"))
        self.table.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(results, orient="vertical", command=self.table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.bind("<<TreeviewSelect>>", self.show_paper)
        self.table.bind("<Double-1>", self.open_paper)
        detail = ttk.LabelFrame(self, text="선택한 논문 · 초록과 유전자 관련 문장", padding=8)
        detail.grid(row=4, column=0, sticky="nsew", pady=(12, 0))
        detail.columnconfigure(0, weight=1)
        detail.rowconfigure(0, weight=1)
        self.detail = tk.Text(detail, wrap="word", height=9, state="disabled", font="TkDefaultFont")
        self.detail.grid(row=0, column=0, sticky="nsew")
        scroller = ttk.Scrollbar(detail, orient="vertical", command=self.detail.yview)
        scroller.grid(row=0, column=1, sticky="ns")
        self.detail.configure(yscrollcommand=scroller.set)
        ttk.Button(detail, text="선택 논문 링크 열기", command=self.open_paper).grid(row=1, column=0, sticky="e", pady=(6, 0))
        ttk.Label(self, text="인터넷 연결 필요 · 초록 문장은 원문 발췌입니다 · 검색 결과의 실험 종은 혼합될 수 있습니다.",
                  foreground="#5b6570").grid(row=5, column=0, sticky="w", pady=(10, 0))

    def choose_folder(self):
        folder = filedialog.askdirectory(parent=self.root, title="보고서 저장 폴더 선택")
        if folder:
            self.output.set(folder)

    def start_search(self):
        if self.busy:
            return
        try:
            gene, limit, sort = validate_search(self.gene.get(), self.count.get(), self.sort.get())
            if not self.output.get().strip():
                raise ValueError("저장 폴더를 선택하세요.")
            output = Path(self.output.get()).expanduser()
        except ValueError as exc:
            messagebox.showerror("입력 확인", str(exc), parent=self.root)
            return
        self.busy = True
        self.search_button.configure(state="disabled")
        self.spinner.start(10)
        self.status.set("검색 준비 중…")
        # Capture widget values on the GUI thread. The worker only sends queue events.
        options = dict(context=self.context.get().strip(), sort=sort, limit=limit,
                       include_aliases=self.aliases.get(), cache=user_cache_dir())
        threading.Thread(target=self._search_worker, args=(gene, options, output), daemon=True).start()

    def _search_worker(self, gene, options, output):
        try:
            report = search_literature(gene, **options,
                                      progress=lambda text: self.events.put(("status", text)))
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            destination = output / f"{report['gene']['symbol']}-{stamp}"
            save_report(report, destination)
            self.events.put(("done", (report, destination)))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def _poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "status":
                    self.status.set(payload)
                else:
                    self.busy = False
                    self.spinner.stop()
                    self.search_button.configure(state="normal")
                    if kind == "done":
                        self._show_results(*payload)
                    else:
                        self.status.set("검색에 실패했습니다. 입력과 인터넷 연결을 확인하세요.")
                        messagebox.showerror("검색 오류", payload, parent=self.root)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _show_results(self, report, destination):
        self.report, self.report_dir = report, destination
        self.table.delete(*self.table.get_children())
        for index, paper in enumerate(report["papers"]):
            self.table.insert("", "end", iid=str(index), text=paper["title"],
                              values=(paper["year"], paper["journal"], paper["category"], paper["cited_by_count"]))
        self.report_button.configure(state="normal")
        self.csv_button.configure(state="normal")
        self.status.set(f"{report['gene']['symbol']} · {report['total_hits']:,}건 중 {len(report['papers'])}건 · 저장 완료")
        self._set_detail("검색 조건에 맞는 논문이 없습니다. 관심 주제를 바꾸거나 비워서 검색해보세요.")
        if report["papers"]:
            self.table.selection_set("0")
            self.table.focus("0")
            self.show_paper()

    def _set_detail(self, text):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def selected_paper(self):
        selected = self.table.selection()
        return self.report["papers"][int(selected[0])] if selected and self.report else None

    def show_paper(self, event=None):
        paper = self.selected_paper()
        if paper:
            excerpts = "\n\n".join(paper["gene_excerpt"]) or "제공된 초록에서 일치 문장을 찾지 못했습니다."
            self._set_detail(f"{paper['title']}\n{paper['authors']}\n{paper['journal']} ({paper['year']})\n"
                             f"PMID: {paper['pmid'] or '-'}    DOI: {paper['doi'] or '-'}\n\n"
                             f"[유전자 관련 원문 문장]\n{excerpts}\n\n"
                             f"[전체 제공 초록]\n{paper['abstract'] or '초록이 제공되지 않았습니다.'}")

    def open_paper(self, event=None):
        paper = self.selected_paper()
        if paper:
            webbrowser.open(paper["pubmed_url"] or paper["url"])

    def open_report(self):
        if self.report_dir:
            webbrowser.open((self.report_dir / "report.html").resolve().as_uri())

    def export_csv(self):
        if not self.report_dir:
            return
        path = filedialog.asksaveasfilename(parent=self.root, title="CSV 저장", defaultextension=".csv",
                                          initialfile=f"{self.report['gene']['symbol']}-papers.csv",
                                          filetypes=[("CSV", "*.csv")])
        if path:
            try:
                source = self.report_dir / "papers.csv"
                if Path(path).resolve() != source.resolve():
                    shutil.copyfile(source, path)
                self.status.set(f"CSV 저장 완료: {path}")
            except OSError as exc:
                messagebox.showerror("저장 오류", str(exc), parent=self.root)


def main():
    root = tk.Tk()
    if "--smoke-test" in sys.argv:
        # Used by CI to prove the packaged Tcl/Tk runtime actually starts.
        root.withdraw()
        app = LiteratureApp(root)
        root.update()
        import certifi
        assert Path(certifi.where()).is_file(), "Missing bundled HTTPS certificate store"
        assert app.gene.get() == ""
        result = {"version": VERSION, "platform": sys.platform,
                  "tk": root.tk.call("info", "patchlevel"), "ok": True}
        if "--smoke-output" in sys.argv:
            target = Path(sys.argv[sys.argv.index("--smoke-output") + 1])
            target.write_text(json.dumps(result), encoding="utf-8")
        root.destroy()
        return
    LiteratureApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
