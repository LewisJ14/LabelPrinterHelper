from io import BytesIO
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from barcode import Code128
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont


LABEL_WIDTH_MM = 101.6
LABEL_HEIGHT_MM = 101.2
DEFAULT_DPI = 203


def _font(size_pt: float, bold: bool = False, dpi: int = DEFAULT_DPI):
    filename = "calibrib.ttf" if bold else "calibri.ttf"
    path = Path("C:/Windows/Fonts") / filename
    size = max(8, round(size_pt * dpi / 72))
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def _fit_image(image: Image.Image, size: Tuple[int, int]) -> Image.Image:
    copy = image.convert("RGBA")
    copy.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, "white")
    x = (size[0] - copy.width) // 2
    y = (size[1] - copy.height) // 2
    canvas.alpha_composite(copy, (x, y))
    return canvas.convert("RGB")


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: Tuple[int, int, int, int],
    size_pt: float,
    bold: bool,
    dpi: int,
    max_lines: int,
) -> None:
    x1, y1, x2, y2 = box
    words = str(text or "").split()
    if not words:
        return
    for candidate_pt in range(round(size_pt), 6, -1):
        font = _font(candidate_pt, bold=bold, dpi=dpi)
        lines = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if draw.textbbox((0, 0), candidate, font=font)[2] <= x2 - x1:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        line_height = draw.textbbox((0, 0), "Ag", font=font)[3] + max(1, dpi // 50)
        if len(lines) <= max_lines and line_height * len(lines) <= y2 - y1:
            draw.multiline_text((x1, y1), "\n".join(lines), font=font, fill="black", spacing=1)
            return


def _barcode_image(value: str, width: int, height: int) -> Image.Image:
    buffer = BytesIO()
    Code128(str(value or ""), writer=ImageWriter()).write(
        buffer,
        options={
            "write_text": False,
            "quiet_zone": 1.0,
            "module_width": 0.35,
            "module_height": 18,
            "dpi": DEFAULT_DPI,
        },
    )
    image = Image.open(buffer).convert("RGB")
    return image.resize((width, height), Image.Resampling.NEAREST)


def render_label(
    payload: Dict,
    output_path: Path,
    branding: Optional[Dict] = None,
    logo_loader: Optional[Callable[[str], bytes]] = None,
    dpi: int = DEFAULT_DPI,
) -> Path:
    label = payload.get("label") or payload
    px_per_mm = dpi / 25.4

    def mm(value: float) -> int:
        return round(value * px_per_mm)

    canvas = Image.new(
        "RGB",
        (mm(LABEL_WIDTH_MM), mm(LABEL_HEIGHT_MM)),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    heading = " ".join(
        part
        for part in (
            str(label.get("manufacturer") or "").strip(),
            str(label.get("model") or "").strip(),
            str(label.get("cpu") or "").strip(),
            f"Video: {label.get('gpu')}" if label.get("gpu") else "",
            f"Grade: {label.get('grade')}" if label.get("grade") else "",
        )
        if part
    )
    specification = ", ".join(
        part
        for part in (
            str(label.get("ssd") or "").strip(),
            str(label.get("ram") or "").strip(),
            str(label.get("resolution") or "").strip(),
            "Touchscreen" if label.get("touchscreen") else "",
            str(label.get("observations") or "").strip(),
            "Webcam" if label.get("webcam") else "",
        )
        if part
    )
    _draw_wrapped(
        draw,
        heading,
        (mm(1.27), mm(1.27), mm(96.52), mm(15.24)),
        12,
        True,
        dpi,
        3,
    )
    _draw_wrapped(
        draw,
        specification,
        (mm(1.27), mm(16.51), mm(95.25), mm(36.83)),
        11,
        False,
        dpi,
        4,
    )
    audit = (
        f"Technician: {label.get('technician') or '—'}\n"
        f"Audit Date: {label.get('audit_date') or '—'}\n"
        f"Lot ID: {label.get('lot_id') or '—'}\n"
        f"Unit ID: {label.get('unit_id') or '—'}\n"
        f"PO: {label.get('po_number') or '—'}"
    )
    draw.multiline_text(
        (mm(1.27), mm(33.02)),
        audit,
        fill="black",
        font=_font(11, dpi=dpi),
        spacing=max(1, mm(0.25)),
    )

    brand = branding or {}
    logo = None
    logo_url = str(brand.get("logo_url") or "").strip()
    if logo_url and logo_loader:
        try:
            logo = Image.open(BytesIO(logo_loader(logo_url)))
        except Exception:
            logo = None

    def draw_logo(x: float, y: float) -> None:
        box = (mm(21.59), mm(12.7))
        if logo is not None:
            fitted = _fit_image(logo, box)
            canvas.paste(fitted, (mm(x), mm(y)))
            return
        colour = str(brand.get("primary_color") or "#27845b")
        left, top = mm(x + 1.8), mm(y + 1.35)
        right, bottom = mm(x + 19.8), mm(y + 11.35)
        draw.rounded_rectangle((left, top, right, bottom), radius=mm(1.5), fill=colour)
        mark = str(brand.get("logo_text") or "PC")[:3].upper()
        font = _font(14, bold=True, dpi=dpi)
        bounds = draw.textbbox((0, 0), mark, font=font)
        draw.text(
            ((left + right - (bounds[2] - bounds[0])) // 2, (top + bottom - (bounds[3] - bounds[1])) // 2),
            mark,
            font=font,
            fill="white",
        )

    draw_logo(68.58, 31.75)
    grade = str(label.get("grade") or "")
    grade_font = _font(14, dpi=dpi)
    grade_box = (mm(67.31), mm(46.99), mm(95.25), mm(57.15))
    draw.text(
        ((grade_box[0] + grade_box[2]) // 2, (grade_box[1] + grade_box[3]) // 2),
        grade,
        font=grade_font,
        fill="black",
        anchor="mm",
    )

    serial = str(label.get("serial_number") or "").strip()
    draw.text((mm(12.7), mm(60.96)), "Serial Number:", font=_font(10, dpi=dpi), fill="black")
    upper_barcode = _barcode_image(serial, mm(57.15), mm(6.2))
    canvas.paste(upper_barcode, (mm(41.91), mm(58.42)))
    serial_font = _font(9, bold=True, dpi=dpi)
    draw.text((mm(70.485), mm(65.8)), serial, font=serial_font, fill="black", anchor="mm")
    draw.text(
        (mm(58.42), mm(70.485)),
        str(label.get("unit_id") or ""),
        font=_font(22, dpi=dpi),
        fill="black",
        anchor="mm",
    )

    tear_barcode = _barcode_image(serial, mm(60.96), mm(9.5))
    canvas.paste(tear_barcode, (mm(15.24), mm(83.82)))
    draw.text(
        (mm(45.72), mm(95.3)),
        serial,
        font=_font(10, bold=True, dpi=dpi),
        fill="black",
        anchor="mm",
    )
    draw_logo(78.74, 83.82)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", dpi=(dpi, dpi))
    return output_path
