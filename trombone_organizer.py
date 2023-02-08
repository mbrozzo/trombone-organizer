from dataclasses import dataclass
import typing
from typing import Any, Optional, Callable, TypeAlias
from pathlib import Path
import json
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

DIR_KEY = "Directory"


def fatal_error(text: str = "", title: str = "Fatal Error", exception: Exception | None = None):
    err_win = tk.Tk()
    err_win.resizable(0, 0)
    err_win.title(title)
    if text:
        err_text = ttk.Label(err_win, text=text)
        err_text.pack(padx=10, pady=10)
    if exception:
        err_text = ttk.Label(err_win, text=str(exception))
        err_text.pack(padx=10, pady=10)
    err_win.mainloop()
    exit(1)


def get_current_font() -> tkfont.Font:
    style = ttk.Style()
    font_name = style.lookup("My.TLabel", "font")
    font = tkfont.nametofont(font_name)
    return font


def one_line_validate(text: str) -> bool:
    return len(text.splitlines()) <= 1


def difficulty_validate(difficulty: int) -> bool:
    return difficulty > 0 and difficulty <= 10


def note_color_validate(color: tuple[float, float, float]) -> bool:
    return all([v >= 0 and v <= 1 for v in color])


@dataclass
class ColSpec:
    key: str | None
    width: int = 200
    data_type: TypeAlias = str
    validate: Callable[[data_type], bool] | None = one_line_validate if data_type == str else None


class ChartDataTable(tk.Frame):
    def __init__(self, master, columns: list[ColSpec], chart_data_by_dir: dict[dict[str, Any]], *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self._columns: list[ColSpec] = columns
        self._chart_data_by_dir: dict[dict[str, Any]] = chart_data_by_dir
        self._chart_updates_by_dir: dict[dict[str, Any]] = {}
        self._border: int = 1
        self._sorted_column = None
        self._sorted_reverse = False

        # Treeview initialization
        col_keys = [col.key for col in self._columns]
        self._treeview: ttk.Treeview = ttk.Treeview(self, columns=col_keys, show="headings")
        treeview = self._treeview
        treeview.grid(row=0, column=0, sticky=tk.NSEW)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Columns
        for col in self._columns:
            treeview.column(col.key, width=col.width)
            treeview.heading(col.key, text=col.key)

        # Rows
        for chart_dir in chart_data_by_dir:
            chart_data = chart_data_by_dir[chart_dir]
            vals = [chart_dir] + [chart_data.get(key, "") for key in col_keys[1:]]
            treeview.insert("", tk.END, values=vals, iid=chart_dir)
        treeview.tag_configure("white", background="#ffffff")
        treeview.tag_configure("gray", background="#dddddd")
        treeview.tag_configure("edited", background="#9999ff")
        self._color_lines()

        # Scrollbars
        self._scrollbar_v: ttk.Scrollbar = ttk.Scrollbar(self, orient="vertical", command=treeview.yview)
        scrollbar_v = self._scrollbar_v
        scrollbar_v.grid(row=0, column=1, sticky=tk.NS)
        treeview["yscrollcommand"] = scrollbar_v.set

        self._scrollbar_h: ttk.Scrollbar = ttk.Scrollbar(self, orient="horizontal", command=treeview.xview)
        scrollbar_h = self._scrollbar_h
        scrollbar_h.grid(row=1, column=0, sticky=tk.EW)
        treeview["xscrollcommand"] = scrollbar_h.set

        # Edit field
        self._edit_frame: tk.Frame = tk.Frame(self._treeview, background="black")
        font = get_current_font()
        font_spec = (font.cget("family"), font.cget("size"), font.cget("weight"))
        self._edit_field: tk.Text = tk.Text(self._edit_frame, font=font_spec)
        self._edit_field.pack(expand=True, fill=tk.BOTH, padx=self._border, pady=self._border)
        self._edit_coords: tuple[str, ...] | None = None
        self._edit_field.bind("<Return>", self._on_edit_confirmation)

        # Events
        self._treeview.bind("<Button-1>", self._on_click_treeview)
        self._treeview.bind("<Double-Button-1>", self._on_double_click_treeview)
        self._edit_field.bind("<FocusOut>", self._on_lose_focus_edit_field)

    def _get_items(self) -> tuple[str, ...]:
        items = self._treeview.get_children("")
        return items

    def _color_lines(self):
        items = self._get_items()
        is_gray = True
        for item in items:
            tag = "edited" if item in self._chart_updates_by_dir else "gray" if is_gray else "white"
            self._treeview.item(item, tags=tag)
            is_gray = not is_gray

    def _get_column_heading(self, col: str) -> str:
        return self._treeview.heading(col, option="text")

    def _edit_cell(self, row: str, col: str):
        self._edit_coords = (row, col)
        old_val: str = self._treeview.set(row, column=col)
        x, y, w, h = self._treeview.bbox(row, column=col)
        border = self._border
        self._edit_frame.place(x=x - border, y=y - border, width=w + 2 * border, height=h + 2 * border)
        self._edit_field.delete(1.0, tk.END)
        self._edit_field.insert(tk.END, old_val)
        self._edit_field.focus()

    def _edit_field_hide(self):
        self._edit_frame.place_forget()

    def _sort_by_column(self, col: str, reverse: bool = False):
        tree = self._treeview
        items = list(self._get_items())
        items.sort(key=lambda item: tree.set(item, col), reverse=reverse)
        for i, item in enumerate(items):
            tree.move(item, "", i)
        self._color_lines()

    def _get_column_specification(self, column: str) -> ColSpec:
        return self._columns[int(column[1:]) - 1]

    def _on_click_treeview(self, event: tk.Event):
        region = self._treeview.identify_region(event.x, event.y)
        if region == "heading":
            col = self._treeview.identify_column(event.x)
            if self._sorted_column == col:
                self._sort_by_column(col, reverse=(not self._sorted_reverse))
                self._sorted_reverse = not self._sorted_reverse
            else:
                self._sort_by_column(col)
                self._sorted_column = col
                self._sorted_reverse = False
            return

    def _on_double_click_treeview(self, event: tk.Event):
        region = self._treeview.identify_region(event.x, event.y)
        if region == "cell":
            col = self._treeview.identify_column(event.x)
            if self._get_column_heading(col) == DIR_KEY:
                return
            row = self._treeview.identify_row(event.y)
            self._edit_cell(row, col)
            return
        if region == "heading":
            self._on_click_treeview(event)
            return

    def _on_lose_focus_edit_field(self, event: tk.Event):
        self._edit_field_hide()

    def _on_edit_confirmation(self, event: tk.Event):
        new_val_str = self._edit_field.get("1.0", tk.END)[:-1]
        row, col = self._edit_coords
        self._edit_field_hide()

        col_spec = self._get_column_specification(col)
        if not col_spec.data_type == str and new_val_str=="":
            new_val_str = str(None)
            new_val = None
        else:
            try:
                data_type_origin = typing.get_origin(col_spec.data_type)
                data_type_args = typing.get_args(col_spec.data_type)
                if data_type_origin == tuple:
                    new_val = new_val_str.split()
                    if data_type_args:
                        if len(data_type_args) != len(new_val):
                            raise TypeError()
                        new_val = [t(v) for v, t in zip(new_val, data_type_args)]
                if data_type_origin == list:
                    new_val = new_val_str.split()
                    if data_type_args:
                        new_val = [data_type_args[0](v) for v in new_val]
                else:
                    new_val = col_spec.data_type(new_val_str)
            except:
                print("ERROR: New value has wrong data type.")
                return
            if not col_spec.validate is None and not col_spec.validate():
                print("ERROR: Invalid new value.")
                return

        self._treeview.set(row, column=col, value=new_val_str)
        if row not in self._chart_updates_by_dir:
            self._chart_updates_by_dir[row] = {col: new_val_str}
        else:
            self._chart_updates_by_dir[row][col] = new_val
        self._color_lines()


@dataclass
class ChartReadError:
    severity: str
    message: str
    chart: str
    exception: Optional[Exception] = None


def read_chart_data(charts_dir: Path) -> tuple[dict[str, dict], list[ChartReadError]]:
    chart_data_by_dir: dict[str, dict] = {}
    errors: list[ChartReadError] = []
    for chart_dir in charts_dir.iterdir():
        if not chart_dir.is_dir():
            continue

        chart_data_file = chart_dir / "song.tmb"

        if not chart_data_file.exists():
            errors.append(
                ChartReadError(chart=chart_dir.name, severity="Warning", message="No data file, song skipped.")
            )
            continue

        try:
            with chart_data_file.open(encoding="utf8") as chart_stream:
                chart_data: dict = json.load(chart_stream)
        except Exception as e:
            errors.append(
                ChartReadError(
                    chart=chart_dir.name,
                    severity="Error",
                    message="Could not read JSON data, song skipped.",
                    exception=e,
                )
            )
            continue

        if not type(chart_data) == dict:
            errors.append(
                ChartReadError(
                    chart=chart_dir.name, severity="Error", message="JSON data from is not a dictionary, song skipped."
                )
            )
            continue

        chart_data_by_dir[chart_dir.name] = chart_data

    return chart_data_by_dir, errors


def main():
    try:
        charts_dir_win = tk.Tk()
        charts_dir_win.title("Trombone Organizer")

        charts_dir_text = ttk.Label(charts_dir_win, text="Trombone Champ custom songs directory:")
        charts_dir_text.pack()
        charts_dir_var = tk.StringVar(
            value="C:\Program Files (x86)\Steam\steamapps\common\TromboneChamp\BepInEx\CustomSongs"
        )
        charts_dir_box = ttk.Entry(charts_dir_win, textvariable=charts_dir_var, width=100)
        charts_dir_box.pack(fill=tk.X, padx=5, pady=5)
        charts_dir_box.focus()
        charts_dir_ok = ttk.Button(charts_dir_win, text="OK", width=10, command=charts_dir_win.destroy)
        charts_dir_ok.pack()

        charts_dir_win.bind("<Return>", lambda event: charts_dir_win.destroy())

        charts_dir_win.mainloop()

        charts_dir = Path(charts_dir_var.get())
        try:
            chart_data_by_dir, errors = read_chart_data(charts_dir)
        except Exception as e:
            fatal_error(text="Could not read custom song data from the specified directory.", exception=e)

        main_win = tk.Tk()
        main_win.geometry("890x400")
        main_win.state("zoomed")
        main_win.title("Trombone Organizer")

        if errors:
            errors_report = tk.Toplevel(main_win)
            errors_report.title("Custom song error report")
            cols = [
                "Chart directory",
                "Severity",
                "Message",
                "Exception",
            ]
            errors_table = ttk.Treeview(errors_report, show="headings", columns=cols)
            errors_table.pack()

            for col in cols:
                errors_table.heading(col, text=col)

            errs = [(err.chart, err.severity, err.message, str(err.exception)) for err in errors]
            errs.sort()
            for err_vals in errs:
                errors_table.insert("", tk.END, values=err_vals)

        menubar = tk.Menu(main_win)
        main_win.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Exit", command=main_win.destroy)
        menubar.add_cascade(label="File", menu=file_menu, underline=0)

        cols = [
            ColSpec(key=DIR_KEY, width=80),
            ColSpec(key="trackRef", width=80),
            ColSpec(key="shortName"),
            ColSpec(key="name", width=250),
            ColSpec(key="author", width=150),
            ColSpec(key="year", width=40, data_type=int),
            ColSpec(key="genre", width=100),
            ColSpec(key="description", width=600, validate=None),
            ColSpec(key="difficulty", width=40, data_type=int, validate=difficulty_validate),
            ColSpec(key="tempo", width=40, data_type=float),
            ColSpec(key="timesig", width=40, data_type=int),
            ColSpec(key="endpoint", width=40, data_type=float),
            ColSpec(key="savednotespacing", width=40, data_type=float),
            ColSpec(key="note_color_start", data_type=tuple[float, float, float], validate=note_color_validate),
            ColSpec(key="note_color_end", data_type=tuple[float, float, float], validate=note_color_validate),
            # ColSpec(key="bgdata"),
            ColSpec(key="UNK1", width=50, data_type=int),
            # ColSpec(key="notes"),
            # ColSpec(key="lyrics"),
        ]
        main_win.grid_rowconfigure(0, weight=1)
        main_win.grid_columnconfigure(0, weight=1)
        table = ChartDataTable(main_win, cols, chart_data_by_dir)
        table.grid(row=0, column=0, sticky=tk.NSEW)

        main_win.mainloop()
    except Exception as e:
        fatal_error(exception=e)


if __name__ == "__main__":
    main()
