# Astro Label Printer

A Windows desktop helper that automatically prints a stock label after a device is successfully second checked in Astro.

## Current workflow

1. Sign in with a normal Astro user account. The password is used only for the active session and is never saved.
2. Select the Windows label printer.
3. Select one or more Second Checking operators.
4. Start monitoring.
5. Astro is checked every few seconds for newly completed second-check reports. Matching operators are queued and printed once.

The helper uses the specification saved against the completed check, with the stock unit as a fallback for fields the check did not report. It uses the same 101.6 × 101.2 mm main-and-tear-off layout as Astro's manual stock label.

## Safety and reliability

- The first connection starts at the newest existing report, preventing an accidental historical print run.
- A local SQLite queue records pending, printed, ignored and failed jobs.
- Restarting the program does not print successful jobs again.
- Failed jobs stay visible and can be retried.
- Operator selections and the chosen printer are saved locally; passwords are not.
- The label is always rendered at its physical size. Configure the printer driver with a 101.6 × 101.2 mm (approximately 4 × 4 inch) stock size and no scaling.

## Install

Run `Setup.ps1` once from PowerShell, followed by `Build.ps1`. Then use
`Start Label Printer.bat`. The launcher uses the compiled executable when it is
available and falls back to the local Python environment during development.

For development:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

## Astro dependency

The corresponding Web-Tools version must expose the authenticated endpoint:

```text
GET /api/stock_units/label-queue
```

The endpoint is session-authenticated and read-only. The desktop helper signs in through Astro's normal login form.

## Suggested next steps

- Add a packaged `.exe` and signed installer.
- Add a printer calibration page for margins and darkness.
- Add a tray icon and optional start-with-Windows setting.
- Add an Astro-side “Send to label printer” action for manual reprints.
- Add workstation names if more than one helper will serve different printers.

## Publishing a release

`publish-release.ps1` follows the SecondChecking release pattern. It increments
the patch version when no version is supplied, compiles a fresh executable,
writes `update.json`, and uploads both files to a GitHub release.

```powershell
.\publish-release.ps1 -Notes "Describe the release"
```

For an explicit version, such as the first release:

```powershell
.\publish-release.ps1 -Version "0.1.0" -Notes "Initial release"
```
