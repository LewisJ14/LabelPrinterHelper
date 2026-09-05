from PIL import Image
import pytest

from label_printer_helper.label_renderer import render_label


def sample_payload():
    return {
        "label": {
            "manufacturer": "LENOVO",
            "model": "THINKPAD T14 GEN 2",
            "cpu": "i5-1135G7",
            "gpu": "Intel Iris Xe",
            "grade": "A",
            "ssd": "256GB SSD",
            "ram": "16GB RAM",
            "resolution": "1920 x 1080",
            "touchscreen": True,
            "observations": "Light cosmetic wear",
            "webcam": True,
            "technician": "Lewis",
            "audit_date": "05-09-2026",
            "lot_id": "141472",
            "unit_id": "900001053",
            "po_number": "PO-0304",
            "serial_number": "PF1EX81X",
        }
    }


def test_label_renders_at_the_configured_physical_size(tmp_path):
    output = render_label(sample_payload(), tmp_path / "label.png")

    with Image.open(output) as image:
        assert image.size == (812, 809)
        assert image.info["dpi"][0] == pytest.approx(203.0, abs=0.01)


def test_label_renders_without_a_remote_logo(tmp_path):
    output = render_label(
        sample_payload(),
        tmp_path / "fallback.png",
        branding={"logo_text": "PC", "primary_color": "#37a772"},
    )

    assert output.exists()
    assert output.stat().st_size > 1000
