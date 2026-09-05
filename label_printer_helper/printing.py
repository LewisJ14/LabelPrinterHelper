from pathlib import Path
from typing import List

import win32con
import win32print
import win32ui
from PIL import Image, ImageWin


def available_printers() -> List[str]:
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    names = [item[2] for item in win32print.EnumPrinters(flags)]
    return sorted(set(names), key=str.casefold)


def default_printer() -> str:
    try:
        return win32print.GetDefaultPrinter()
    except Exception:
        return ""


def print_label(image_path: Path, printer_name: str, document_name: str) -> None:
    if not printer_name:
        raise RuntimeError("Choose a label printer first.")
    image = Image.open(image_path).convert("RGB")
    dc = win32ui.CreateDC()
    try:
        dc.CreatePrinterDC(printer_name)
        printable_width = dc.GetDeviceCaps(win32con.HORZRES)
        printable_height = dc.GetDeviceCaps(win32con.VERTRES)
        printer_dpi_x = dc.GetDeviceCaps(win32con.LOGPIXELSX)
        printer_dpi_y = dc.GetDeviceCaps(win32con.LOGPIXELSY)
        target_width = round((101.6 / 25.4) * printer_dpi_x)
        target_height = round((101.2 / 25.4) * printer_dpi_y)
        fit_scale = min(
            1.0,
            printable_width / target_width,
            printable_height / target_height,
        )
        draw_width = max(1, round(target_width * fit_scale))
        draw_height = max(1, round(target_height * fit_scale))
        left = (printable_width - draw_width) // 2
        top = (printable_height - draw_height) // 2
        dc.StartDoc(document_name[:120])
        try:
            dc.StartPage()
            ImageWin.Dib(image).draw(
                dc.GetHandleOutput(),
                (left, top, left + draw_width, top + draw_height),
            )
            dc.EndPage()
        finally:
            dc.EndDoc()
    finally:
        dc.DeleteDC()
