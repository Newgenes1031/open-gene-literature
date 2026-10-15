"""GUI integration check using a synthetic article; no network or personal files."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gene_literature import VERSION, normalize
from gene_literature_gui import LiteratureApp


def wait_finished(root, app):
    deadline = time.monotonic() + 8
    while app.busy and time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)
    assert not app.busy, "Worker did not finish"


def main():
    root = tk.Tk()
    root.withdraw()
    app = LiteratureApp(root)
    try:
        with patch("gene_literature_gui.messagebox.showerror") as error:
            app.start_search()
            error.assert_called_once()
        paper = normalize({"title": "FASN synthetic GUI test", "pmid": "1", "id": "1", "source": "MED",
                           "pubYear": "2026", "abstractText": "FASN was measured in this synthetic test."}, ["FASN"])
        report = {"version": VERSION, "gene": {"symbol": "FASN", "name": "fatty acid synthase", "hgnc_id": "HGNC:3594"},
                  "papers": [paper], "total_hits": 1, "query": "synthetic", "sort": "relevance",
                  "created_at": datetime.now(timezone.utc).isoformat(), "include_aliases": False}
        with tempfile.TemporaryDirectory() as folder:
            app.output.set(folder)
            app.gene.set("FASN")
            with patch("gene_literature_gui.search_literature", return_value=report):
                app.start_search()
                assert app.busy
                wait_finished(root, app)
            assert len(app.table.get_children()) == 1
            assert "synthetic test" in app.detail.get("1.0", "end")
            assert (app.report_dir / "report.html").is_file()
            assert (app.report_dir / "papers.csv").is_file()
            with patch("gene_literature_gui.webbrowser.open") as browser:
                app.open_paper()
                browser.assert_called_once_with("https://pubmed.ncbi.nlm.nih.gov/1/")
            target = Path(folder) / "export.csv"
            with patch("gene_literature_gui.filedialog.asksaveasfilename", return_value=str(target)):
                app.export_csv()
            assert target.is_file()
            with patch("gene_literature_gui.search_literature", side_effect=ValueError("synthetic failure")), \
                    patch("gene_literature_gui.messagebox.showerror") as error:
                app.start_search()
                wait_finished(root, app)
                error.assert_called_once()
            assert str(app.search_button["state"]) == "normal"
        print("GUI integration: validation, worker completion, article preview, links, report/CSV export and error recovery passed.")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
