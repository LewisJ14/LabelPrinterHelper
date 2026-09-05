import os
import threading
from datetime import datetime
from pathlib import Path
from tkinter import Listbox, StringVar, messagebox
from typing import Dict, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, DISABLED, END, LEFT, NORMAL, RIGHT, X, Y

from . import __version__
from .api import AstroApiError, AstroClient
from .config import AppConfig, app_data_dir
from .label_renderer import render_label
from .printing import available_printers, default_printer, print_label
from .store import QueueStore


class LabelPrinterApp:
    def __init__(self):
        self.config = AppConfig.load()
        self.store = QueueStore(app_data_dir() / "queue.db")
        self.client: Optional[AstroClient] = None
        self.branding: Dict = {}
        self.monitoring = False
        self.selected_users = set(self.config.selected_users)
        self.stop_event = threading.Event()
        self.poll_lock = threading.Lock()

        self.root = ttk.Window(themename="flatly")
        self.root.title(f"Astro Label Printer {__version__}")
        self.root.geometry("1120x720")
        self.root.minsize(980, 640)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self.status_var = StringVar(value="Sign in to connect to Astro.")
        self.connection_var = StringVar(value="Not connected")
        self.monitor_var = StringVar(value="Start monitoring")
        self.queue_var = StringVar(value="0 waiting")
        self._build_login()
        self._build_dashboard()
        self.dashboard.pack_forget()

    def run(self) -> None:
        self.root.mainloop()

    def _build_login(self) -> None:
        self.login_view = ttk.Frame(self.root, padding=36)
        self.login_view.pack(fill=BOTH, expand=True)
        shell = ttk.Frame(self.login_view, padding=32, bootstyle="light")
        shell.place(relx=0.5, rely=0.48, anchor="center", width=510)
        ttk.Label(shell, text="ASTRO", font=("Segoe UI", 11, "bold"), bootstyle="success").pack(anchor="w")
        ttk.Label(shell, text="Label Printer", font=("Segoe UI", 28, "bold")).pack(anchor="w", pady=(2, 6))
        ttk.Label(
            shell,
            text="Sign in with your Astro account to monitor completed second checks.",
            bootstyle="secondary",
            wraplength=430,
        ).pack(anchor="w", pady=(0, 24))

        ttk.Label(shell, text="Astro address", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.url_entry = ttk.Entry(shell)
        self.url_entry.insert(0, self.config.astro_url)
        self.url_entry.pack(fill=X, pady=(5, 14))
        ttk.Label(shell, text="Username", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.username_entry = ttk.Entry(shell)
        self.username_entry.insert(0, self.config.last_username)
        self.username_entry.pack(fill=X, pady=(5, 14))
        ttk.Label(shell, text="Password", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.password_entry = ttk.Entry(shell, show="•")
        self.password_entry.pack(fill=X, pady=(5, 20))
        self.password_entry.bind("<Return>", lambda _event: self._sign_in())
        self.sign_in_button = ttk.Button(shell, text="Sign in", command=self._sign_in, bootstyle="success")
        self.sign_in_button.pack(fill=X)
        ttk.Label(
            shell,
            text="Your password is used only to create this session and is never saved.",
            font=("Segoe UI", 9),
            bootstyle="secondary",
        ).pack(anchor="w", pady=(12, 0))

    def _build_dashboard(self) -> None:
        self.dashboard = ttk.Frame(self.root, padding=20)
        header = ttk.Frame(self.dashboard)
        header.pack(fill=X, pady=(0, 16))
        title_wrap = ttk.Frame(header)
        title_wrap.pack(side=LEFT)
        ttk.Label(title_wrap, text="ASTRO", font=("Segoe UI", 10, "bold"), bootstyle="success").pack(anchor="w")
        ttk.Label(title_wrap, text="Automatic label printing", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(
            title_wrap,
            text=f"Version {__version__}",
            font=("Segoe UI", 9),
            bootstyle="secondary",
        ).pack(anchor="w", pady=(2, 0))
        connection = ttk.Label(header, textvariable=self.connection_var, padding=(12, 7), bootstyle="success-inverse")
        connection.pack(side=RIGHT)

        content = ttk.Frame(self.dashboard)
        content.pack(fill=BOTH, expand=True)
        sidebar = ttk.Frame(content, width=300)
        sidebar.pack(side=LEFT, fill=Y, padx=(0, 16))
        sidebar.pack_propagate(False)
        main = ttk.Frame(content)
        main.pack(side=LEFT, fill=BOTH, expand=True)

        printer_card = ttk.Labelframe(sidebar, text=" Printer ", padding=16)
        printer_card.pack(fill=X, pady=(0, 14))
        ttk.Label(printer_card, text="Label printer", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.printer_combo = ttk.Combobox(printer_card, state="readonly")
        self.printer_combo.pack(fill=X, pady=(6, 10))
        self.printer_combo.bind("<<ComboboxSelected>>", self._settings_changed)
        ttk.Button(printer_card, text="Refresh printers", command=self._load_printers, bootstyle="secondary-outline").pack(fill=X)

        users_card = ttk.Labelframe(sidebar, text=" Automatically print for ", padding=16)
        users_card.pack(fill=BOTH, expand=True, pady=(0, 14))
        ttk.Label(
            users_card,
            text="Select the people whose completed checks should print automatically.",
            bootstyle="secondary",
            wraplength=250,
        ).pack(anchor="w", pady=(0, 9))
        self.users_list = Listbox(
            users_card,
            selectmode="multiple",
            exportselection=False,
            borderwidth=0,
            highlightthickness=1,
            activestyle="none",
            font=("Segoe UI", 10),
        )
        self.users_list.pack(fill=BOTH, expand=True)
        self.users_list.bind("<<ListboxSelect>>", self._users_changed)

        self.monitor_button = ttk.Button(
            sidebar,
            textvariable=self.monitor_var,
            command=self._toggle_monitoring,
            bootstyle="success",
            padding=10,
        )
        self.monitor_button.pack(fill=X)
        ttk.Button(sidebar, text="Sign out", command=self._sign_out, bootstyle="link").pack(fill=X, pady=(5, 0))

        summary = ttk.Frame(main)
        summary.pack(fill=X, pady=(0, 12))
        self._summary_card(summary, "Status", self.status_var).pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        self._summary_card(summary, "Queue", self.queue_var).pack(side=LEFT, fill=X, expand=True, padx=(8, 0))

        queue_card = ttk.Labelframe(main, text=" Print activity ", padding=12)
        queue_card.pack(fill=BOTH, expand=True)
        actions = ttk.Frame(queue_card)
        actions.pack(fill=X, pady=(0, 10))
        ttk.Button(actions, text="Check now", command=self._check_now, bootstyle="secondary-outline").pack(side=LEFT)
        ttk.Button(actions, text="Preview", command=self._preview_selected, bootstyle="secondary-outline").pack(side=LEFT, padx=7)
        ttk.Button(actions, text="Retry / reprint", command=self._retry_selected, bootstyle="secondary-outline").pack(side=LEFT)

        columns = ("time", "user", "serial", "model", "status")
        self.history = ttk.Treeview(queue_card, columns=columns, show="headings", height=18)
        headings = {
            "time": ("Checked", 145),
            "user": ("Operator", 120),
            "serial": ("Serial number", 125),
            "model": ("Model", 170),
            "status": ("Print status", 110),
        }
        for key, (label, width) in headings.items():
            self.history.heading(key, text=label)
            self.history.column(key, width=width, minwidth=90, anchor="w")
        scrollbar = ttk.Scrollbar(queue_card, command=self.history.yview)
        self.history.configure(yscrollcommand=scrollbar.set)
        self.history.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

    @staticmethod
    def _summary_card(parent, title: str, variable: StringVar):
        card = ttk.Frame(parent, padding=14, bootstyle="light")
        ttk.Label(card, text=title.upper(), font=("Segoe UI", 8, "bold"), bootstyle="secondary").pack(anchor="w")
        ttk.Label(card, textvariable=variable, font=("Segoe UI", 13, "bold"), wraplength=320).pack(anchor="w", pady=(3, 0))
        return card

    def _sign_in(self) -> None:
        url = self.url_entry.get().strip().rstrip("/")
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not url or not username or not password:
            messagebox.showwarning("Sign in", "Enter the Astro address, username and password.")
            return
        self.sign_in_button.configure(state=DISABLED, text="Signing in…")

        def work():
            try:
                client = AstroClient(url)
                payload = client.login(username, password)
                self.root.after(0, lambda: self._signed_in(client, payload, url, username))
            except Exception as exc:
                error = str(exc)
                self.root.after(0, lambda error=error: self._sign_in_failed(error))

        threading.Thread(target=work, daemon=True).start()

    def _signed_in(self, client: AstroClient, payload: Dict, url: str, username: str) -> None:
        self.client = client
        self.branding = payload.get("branding") or {}
        self.config.astro_url = url
        self.config.last_username = username
        self.config.save()
        if self.store.get_cursor() == 0:
            self.store.set_cursor(int(payload.get("latest_report_id") or 0))
        self.password_entry.delete(0, END)
        self._populate_users(payload.get("users") or [])
        self._load_printers()
        self.connection_var.set(f"Connected as {payload.get('authenticated_user') or username}")
        self.status_var.set("Ready to monitor completed second checks.")
        self.sign_in_button.configure(state=NORMAL, text="Sign in")
        self.login_view.pack_forget()
        self.dashboard.pack(fill=BOTH, expand=True)
        self._refresh_history()

    def _sign_in_failed(self, error: str) -> None:
        self.sign_in_button.configure(state=NORMAL, text="Sign in")
        messagebox.showerror("Could not sign in", error)

    def _sign_out(self) -> None:
        self._stop_monitoring()
        if self.client:
            self.client.session.close()
        self.client = None
        self.connection_var.set("Not connected")
        self.dashboard.pack_forget()
        self.login_view.pack(fill=BOTH, expand=True)

    def _populate_users(self, users) -> None:
        self.users_list.delete(0, END)
        selected = {name.casefold() for name in self.config.selected_users}
        for index, name in enumerate(users):
            self.users_list.insert(END, name)
            if str(name).casefold() in selected:
                self.users_list.selection_set(index)
        self._users_changed()

    def _users_changed(self, _event=None) -> None:
        self.selected_users = {
            str(self.users_list.get(index)).strip()
            for index in self.users_list.curselection()
        }
        self.config.selected_users = sorted(self.selected_users, key=str.casefold)
        self.config.save()

    def _load_printers(self) -> None:
        try:
            printers = available_printers()
        except Exception as exc:
            messagebox.showerror("Printers", f"Windows printers could not be loaded.\n\n{exc}")
            return
        self.printer_combo["values"] = printers
        preferred = self.config.printer_name or default_printer()
        if preferred in printers:
            self.printer_combo.set(preferred)
        elif printers:
            self.printer_combo.current(0)
        self._settings_changed()

    def _settings_changed(self, _event=None) -> None:
        self.config.printer_name = self.printer_combo.get().strip()
        self.config.save()

    def _toggle_monitoring(self) -> None:
        if self.monitoring:
            self._stop_monitoring()
            return
        if not self.printer_combo.get().strip():
            messagebox.showwarning("Start monitoring", "Choose the label printer first.")
            return
        if not self.selected_users:
            messagebox.showwarning("Start monitoring", "Select at least one operator first.")
            return
        self.monitoring = True
        self.stop_event.clear()
        self.monitor_var.set("Stop monitoring")
        self.monitor_button.configure(bootstyle="danger")
        self.status_var.set("Monitoring for completed second checks…")
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def _stop_monitoring(self) -> None:
        self.monitoring = False
        self.stop_event.set()
        self.monitor_var.set("Start monitoring")
        self.monitor_button.configure(bootstyle="success")
        if self.client:
            self.status_var.set("Monitoring stopped.")

    def _poll_loop(self) -> None:
        while self.monitoring and not self.stop_event.is_set():
            self._poll_and_print()
            self.stop_event.wait(self.config.poll_seconds)

    def _check_now(self) -> None:
        if not self.client:
            return
        threading.Thread(target=self._poll_and_print, daemon=True).start()

    def _poll_and_print(self) -> None:
        if not self.client or not self.poll_lock.acquire(blocking=False):
            return
        try:
            cursor = self.store.get_cursor()
            while True:
                payload = self.client.fetch_queue(after_id=cursor)
                self.branding = payload.get("branding") or self.branding
                reports = payload.get("reports") or []
                self.store.add_reports(reports, self.selected_users)
                if reports:
                    cursor = max(int(item["report_id"]) for item in reports)
                    self.store.set_cursor(cursor)
                if len(reports) < 100:
                    break
            for job in self.store.pending():
                self._print_job(job)
            self.root.after(0, self._poll_succeeded)
        except AstroApiError as exc:
            error = str(exc)
            self.root.after(
                0,
                lambda error=error: self._poll_failed(error, session_error=True),
            )
        except Exception as exc:
            error = str(exc)
            self.root.after(0, lambda error=error: self._poll_failed(error))
        finally:
            self.poll_lock.release()

    def _print_job(self, job: Dict) -> None:
        report_id = int(job["report_id"])
        serial = str(job["serial_number"] or report_id)
        try:
            image_path = app_data_dir() / "labels" / f"report-{report_id}-{serial}.png"
            render_label(
                job["payload"],
                image_path,
                branding=self.branding,
                logo_loader=self.client.fetch_image if self.client else None,
            )
            print_label(
                image_path,
                self.config.printer_name,
                f"Astro stock label {serial}",
            )
            self.store.set_status(report_id, "printed")
        except Exception as exc:
            self.store.set_status(report_id, "error", str(exc))

    def _poll_succeeded(self) -> None:
        self.status_var.set(
            "Monitoring for completed second checks…" if self.monitoring else "Queue checked."
        )
        self._refresh_history()

    def _poll_failed(self, error: str, session_error: bool = False) -> None:
        self.status_var.set(error)
        if session_error:
            self._stop_monitoring()
            messagebox.showwarning("Astro session ended", error)
        self._refresh_history()

    def _selected_job(self) -> Optional[Dict]:
        selected = self.history.selection()
        if not selected:
            messagebox.showinfo("Print activity", "Select a label from the activity list first.")
            return None
        return self.store.get(int(selected[0]))

    def _preview_selected(self) -> None:
        job = self._selected_job()
        if not job:
            return
        try:
            path = app_data_dir() / "previews" / f"report-{job['report_id']}.png"
            render_label(
                job["payload"],
                path,
                branding=self.branding,
                logo_loader=self.client.fetch_image if self.client else None,
            )
            os.startfile(str(path))
        except Exception as exc:
            messagebox.showerror("Preview label", str(exc))

    def _retry_selected(self) -> None:
        job = self._selected_job()
        if not job:
            return
        self.store.retry(int(job["report_id"]))
        self._refresh_history()
        self._check_now()

    def _refresh_history(self) -> None:
        for item in self.history.get_children():
            self.history.delete(item)
        jobs = self.store.recent()
        waiting = 0
        for job in jobs:
            status = str(job["status"])
            if status == "pending":
                waiting += 1
            checked_at = str(job["checked_at"] or "")
            try:
                checked_at = datetime.fromisoformat(checked_at).strftime("%d/%m/%Y %H:%M")
            except ValueError:
                pass
            self.history.insert(
                "",
                END,
                iid=str(job["report_id"]),
                values=(
                    checked_at,
                    job["checked_by"],
                    job["serial_number"],
                    job["model"],
                    status.title(),
                ),
            )
        self.queue_var.set(f"{waiting} waiting")

    def _close(self) -> None:
        self._stop_monitoring()
        if self.client:
            self.client.session.close()
        self.root.destroy()
