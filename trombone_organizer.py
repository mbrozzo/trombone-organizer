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


def one_line_from_str(s: str) -> str:
    if len(s.splitlines()) > 1:
        raise ValueError("Expected one line.")
    return s


def positive_int_from_str(s: str) -> int:
    if s == "":
        raise ValueError("Expected an integer.")
    n = int(s)
    if n < 0:
        raise ValueError("Expected positive integer.")
    return n


def positive_float_from_str(s: str) -> float | None:
    if s == "":
        raise ValueError("Expected a number.")
    n = float(s)
    if n < 0:
        raise ValueError("Expected positive number.")
    return n


def positive_int_or_none_from_str(s: str) -> int | None:
    if s == "":
        return None
    return positive_int_from_str(s)


def positive_float_or_none_from_str(s: str) -> float | None:
    if s == "":
        return None
    return positive_float_from_str(s)


def difficulty_from_str(s: str) -> int:
    if s == "":
        raise ValueError("Expected an integer.")
    d = int(s)
    if d <= 0 or d > 10:
        raise ValueError("Expected integer between 1 and 10.")
    return d


def note_color_from_str(s: str) -> tuple[float, float, float] | None:
    if s == "":
        return None
    vals_str = s.split()
    if len(vals_str) != 3:
        raise ValueError("Expected 3 values.")
    vals = [float(v) for v in vals_str]
    if any([v < 0 or v > 1 for v in vals]):
        raise ValueError("Expected values between 0 and 1")
    return vals


@dataclass
class ColSpec:
    key: str | None
    width: int = 200
    from_str: Callable[[Any], bool] | None = None


@dataclass
class ChartError:
    severity: str
    message: str
    chart: str
    exception: Optional[Exception] = None


class ChartDataTable(tk.Frame):
    def __init__(self, master, columns: list[ColSpec], charts_dir: Path, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self._columns: list[ColSpec] = columns
        self._charts_dir: Path = charts_dir
        self._chart_updates_by_dir: dict[str, dict[str, Any]] = {}
        self._border: int = 1
        self._sorted_column: str | None = None
        self._sorted_reverse: bool = False

        # Read custom chart data
        self._chart_data_by_dir: dict[dict[str, Any]]
        errors: list[ChartError]
        try:
            self._chart_data_by_dir, errors = self._read_chart_data()
        except Exception as e:
            fatal_error(text="Could not read custom song data from the specified directory.", exception=e)

        # Report errors
        if errors:
            self._show_error_report(errors)

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
        for chart_dir in self._chart_data_by_dir:
            chart_data = self._chart_data_by_dir[chart_dir]
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
        self._edit_field.bind("<Control-Return>", lambda e: None)

        # Events
        self._treeview.bind("<Button-1>", self._on_click_treeview)
        self._treeview.bind("<Double-Button-1>", self._on_double_click_treeview)
        self._edit_field.bind("<FocusOut>", self._on_edit_confirmation)

    def _read_chart_data(self) -> tuple[dict[str, dict], list[ChartError]]:
        chart_data_by_dir: dict[str, dict] = {}
        errors: list[ChartError] = []
        for chart_dir in self._charts_dir.iterdir():
            if not chart_dir.is_dir():
                continue

            chart_data_file = chart_dir / "song.tmb"

            if not chart_data_file.exists():
                errors.append(
                    ChartError(chart=chart_dir.name, severity="Warning", message="No data file, song skipped.")
                )
                continue

            try:
                with chart_data_file.open(encoding="utf8") as chart_stream:
                    chart_data: dict = json.load(chart_stream)
            except Exception as e:
                errors.append(
                    ChartError(
                        chart=chart_dir.name,
                        severity="Error",
                        message="Could not read JSON data, song skipped.",
                        exception=e,
                    )
                )
                continue

            if not type(chart_data) == dict:
                errors.append(
                    ChartError(
                        chart=chart_dir.name,
                        severity="Error",
                        message="JSON data from is not a dictionary, song skipped.",
                    )
                )
                continue

            chart_data_by_dir[chart_dir.name] = chart_data

        return chart_data_by_dir, errors

    def _show_error_report(self, errors: list[ChartError]):
        errors_report = tk.Toplevel()
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
        col_spec = self._get_column_specification(col)
        self._edit_frame.place(
            x=x - border,
            y=y - border,
            width=600 if col_spec.key == "description" else 300,
            height=None if col_spec.key == "description" else h + 2 * border,
        )
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

    def _on_edit_confirmation(self, event: tk.Event):
        new_val_str = self._edit_field.get("1.0", tk.END).strip()
        row, col = self._edit_coords
        self._edit_field_hide()
        if new_val_str == self._treeview.set(row, column=col):
            return

        col_spec = self._get_column_specification(col)
        try:
            new_val = col_spec.from_str(new_val_str)
        except Exception as e:
            print("INFO: Could not update value.")
            print(e)
            print()
            return

        self._treeview.set(row, column=col, value=new_val_str)
        col_heading = self._get_column_heading(col)
        if row not in self._chart_updates_by_dir:
            self._chart_updates_by_dir[row] = {col_heading: new_val_str}
        else:
            self._chart_updates_by_dir[row][col_heading] = new_val
        self._color_lines()

    def apply_edits(self):
        errors = []
        for dir in self._chart_updates_by_dir:
            try:
                with (self._charts_dir / dir / "song.tmb").open(encoding="utf8") as chart_stream:
                    chart_data: dict[str, Any] = json.load(chart_stream)
            except Exception as e:
                errors.append(
                    ChartError(
                        chart=dir,
                        severity="Error",
                        message="Could not read chart data to update, song skipped.",
                        exception=e,
                    )
                )
                continue

            if not type(chart_data) == dict:
                errors.append(
                    ChartError(
                        chart=dir,
                        severity="Error",
                        message="JSON data from is not a dictionary, song skipped.",
                    )
                )
                continue

            updates = self._chart_updates_by_dir[dir]
            chart_data.update(updates)

            for key in updates:
                if updates[key] is None:
                    del chart_data[key]

            try:
                with (self._charts_dir / dir / "song.tmb").open(mode="w", encoding="utf8") as chart_stream:
                    json.dump(chart_data, chart_stream)
            except Exception as e:
                errors.append(
                    ChartError(
                        chart=dir,
                        severity="Error",
                        message="Could not update chart data file.",
                        exception=e,
                    )
                )
                continue

        self._chart_updates_by_dir = {}
        if errors:
            self._show_error_report(errors)
        self._color_lines()


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

        main_win = tk.Tk()
        main_win.geometry("890x400")
        main_win.state("zoomed")
        main_win.title("Trombone Organizer")

        cols = [
            ColSpec(key=DIR_KEY, width=80),
            ColSpec(key="trackRef", width=80, from_str=one_line_from_str),
            ColSpec(key="shortName", from_str=one_line_from_str),
            ColSpec(key="name", width=250, from_str=one_line_from_str),
            ColSpec(key="author", width=150, from_str=one_line_from_str),
            ColSpec(key="year", width=40, from_str=positive_int_from_str),
            ColSpec(key="genre", width=100, from_str=one_line_from_str),
            ColSpec(key="description", width=600),
            ColSpec(key="difficulty", width=40, from_str=difficulty_from_str),
            ColSpec(key="tempo", width=40, from_str=positive_float_from_str),
            ColSpec(key="timesig", width=40, from_str=positive_int_from_str),
            ColSpec(key="endpoint", width=40, from_str=positive_float_from_str),
            ColSpec(key="savednotespacing", width=40, from_str=positive_float_from_str),
            ColSpec(key="note_color_start", from_str=note_color_from_str),
            ColSpec(key="note_color_end", from_str=note_color_from_str),
            # ColSpec(key="bgdata"),
            ColSpec(key="UNK1", width=50, from_str=positive_int_or_none_from_str),
            # ColSpec(key="notes"),
            # ColSpec(key="lyrics"),
        ]
        main_win.grid_rowconfigure(0, weight=1)
        main_win.grid_columnconfigure(0, weight=1)
        table = ChartDataTable(main_win, cols, charts_dir)
        table.grid(row=0, column=0, sticky=tk.NSEW)

        menubar = tk.Menu(main_win)
        main_win.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Apply edits", command=table.apply_edits)
        file_menu.add_command(label="Exit", command=main_win.destroy)
        menubar.add_cascade(label="File", menu=file_menu, underline=0)

        main_win.mainloop()
    except Exception as e:
        fatal_error(exception=e)


if __name__ == "__main__":
    main()
