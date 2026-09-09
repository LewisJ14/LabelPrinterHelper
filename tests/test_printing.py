from label_printer_helper import printing


class FakePrinterDC:
    def CreatePrinterDC(self, printer_name):
        self.printer_name = printer_name

    def GetDeviceCaps(self, capability):
        return 300

    def DeleteDC(self):
        return None


def test_printer_dpi_reads_the_selected_printer_resolution(monkeypatch):
    dc = FakePrinterDC()
    monkeypatch.setattr(printing.win32ui, "CreateDC", lambda: dc)

    assert printing.printer_dpi("Warehouse label printer") == 300
    assert dc.printer_name == "Warehouse label printer"
