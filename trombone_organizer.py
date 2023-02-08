from dataclasses import dataclass
from typing import TypeAlias
from pathlib import Path
import json
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

DIR_KEY = "Directory"


def get_current_font() -> tkfont.Font:
    style = ttk.Style()
    font_name = style.lookup("My.TLabel", "font")
    font = tkfont.nametofont(font_name)
    return font


@dataclass
class ColSpec:
    key: str | None
    width: int = 200
    type: TypeAlias = str


class ChartDataTable(tk.Frame):
    def __init__(self, master, columns: list[ColSpec], chart_data_by_dir: dict[dict], *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self._columns: list[ColSpec] = columns
        self._chart_data_by_dir: dict[dict] = chart_data_by_dir
        self._chart_updates_by_dir: dict[dict] = {}
        self._border: int = 1

        # Treeview initialization and columns
        col_keys = [col.key for col in self._columns]
        treeview = ttk.Treeview(self, columns=col_keys, show="headings")
        treeview.grid(row=0, column=0, sticky="nsew")
        for col in self._columns:
            treeview.column(col.key, width=col.width)
            treeview.heading(col.key, text=col.key)

        # Rows
        treeview.tag_configure("white", background="#ffffff")
        treeview.tag_configure("gray", background="#dddddd")
        is_gray = False
        for chart_dir in chart_data_by_dir:
            chart_data = chart_data_by_dir[chart_dir]
            vals = [chart_dir] + [chart_data.get(key, "") for key in col_keys[1:]]
            treeview.insert("", tk.END, values=vals, tag="gray" if is_gray else "white")
            is_gray = not is_gray

        self._treeview: ttk.Treeview = treeview

        # Scrollbars
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        scrollbar_v = ttk.Scrollbar(self, orient="vertical", command=treeview.yview)
        scrollbar_v.grid(row=0, column=1, sticky=tk.NS)
        treeview["yscrollcommand"] = scrollbar_v.set
        scrollbar_h = ttk.Scrollbar(self, orient="horizontal", command=treeview.xview)
        scrollbar_h.grid(row=1, column=0, sticky=tk.EW)
        treeview["xscrollcommand"] = scrollbar_h.set

        self._scrollbar_v: ttk.Scrollbar = scrollbar_v
        self._scrollbar_h: ttk.Scrollbar = scrollbar_h

        # Edit field
        self._edit_frame: tk.Frame = tk.Frame(self._treeview, background="black")
        font = get_current_font()
        font_spec = (font.cget("family"), font.cget("size"), font.cget("weight"))
        self._edit_field: tk.Text = tk.Text(self._edit_frame, font=font_spec)
        self._edit_field.pack(expand=True, fill=tk.BOTH, padx=self._border, pady=self._border)
        self._edit_coords: tuple[str] | None = None

        # Events
        self._treeview.bind("<Double-Button-1>", self._on_double_click_treeview)
        self._edit_field.bind("<FocusOut>", self._on_lose_focus_edit_field)
        return

    def _on_double_click_treeview(self, event: tk.Event):
        region = self._treeview.identify_region(event.x, event.y)
        if region == "cell":
            col = self._treeview.identify_column(event.x)
            if self._treeview.heading(col, option="text") == DIR_KEY:
                return
            row = self._treeview.identify_row(event.y)
            self._edit_cell(row, col)
            return

    def _on_lose_focus_edit_field(self, event: tk.Event):
        self._edit_frame.place_forget()
        return

    def _edit_cell(self, row: str, col: str):
        old_val: str = self._treeview.set(row, column=col)
        x, y, w, h = self._treeview.bbox(row, column=col)
        border = self._border
        self._edit_frame.place(x=x - border, y=y - border, width=w + 2 * border, height=h + 2 * border)
        self._edit_field.delete(1.0, tk.END)
        self._edit_field.insert(tk.END, old_val)
        self._edit_field.focus()
        return


def read_chart_data(charts_dir: Path) -> dict[str, dict]:
    chart_data_by_dir: dict[str, dict] = {}
    for chart_dir in charts_dir.iterdir():
        chart_data_file = chart_dir / "song.tmb"

        if not chart_data_file.exists():
            continue

        try:
            with chart_data_file.open(encoding="utf8") as chart_stream:
                chart_data: dict = json.load(chart_stream)
        except Exception as e:
            print(f"ERROR: Could not read JSON data from {str(chart_data_file)}, skipping.")
            print(e)
            continue

        if not type(chart_data) == dict:
            print(f"ERROR: JSON data from {str(chart_data_file)} is not a dictionary, skipping.")
            continue

        chart_data_by_dir[chart_dir.name] = chart_data

    return chart_data_by_dir


def main():
    charts_dir = Path(".")
    chart_data_by_dir = read_chart_data(charts_dir)

    root = tk.Tk()
    root.geometry("890x400")
    root.state("zoomed")
    root.title("Trombone Champ Custom Song Manager")

    menubar = tk.Menu(root)
    root.config(menu=menubar)
    file_menu = tk.Menu(menubar, tearoff=False)
    file_menu.add_command(label="Exit", command=root.destroy)
    menubar.add_cascade(label="File", menu=file_menu, underline=0)

    cols = [
        ColSpec(key=DIR_KEY, width=80),
        ColSpec(key="trackRef", width=80),
        ColSpec(key="shortName"),
        ColSpec(key="name", width=250),
        ColSpec(key="author", width=150),
        ColSpec(key="year", width=40),
        ColSpec(key="genre", width=100),
        ColSpec(key="description", width=600),
        ColSpec(key="difficulty", width=40),
        ColSpec(key="tempo", width=40),
        ColSpec(key="timesig", width=40),
        ColSpec(key="endpoint", width=40),
        ColSpec(key="savednotespacing", width=40),
        ColSpec(key="note_color_start"),
        ColSpec(key="note_color_end"),
        # ColSpec(key="bgdata"),
        ColSpec(key="UNK1", width=50),
        # ColSpec(key="notes"),
        # ColSpec(key="lyrics"),
    ]
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    table = ChartDataTable(root, cols, chart_data_by_dir)
    table.grid(row=0, column=0, sticky="nsew")

    root.mainloop()


if __name__ == "__main__":
    main()
