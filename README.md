# 36x Bindery

A **private, local-only PDF desk** from [36XFINANCE](https://www.36xfinance.com/). Merge, split, unlock, lock, compress, and otherwise finish PDFs **on this computer**. Nothing is uploaded. There is no account and no cloud.

Use this repository when the documents must stay in-house: tax files, bank statements, client packs, board papers, identity scans. Do not send those files to a public “free PDF” website.

© 2026 36XFINANCE. All rights reserved. Source is released under the MIT License (see `LICENSE`).

## Privacy contract

- Listens only on `127.0.0.1` (this PC). Other machines on the network cannot reach it.
- Processing stays in a local `.sessions` folder. You download a **new copy**. Originals are not overwritten.
- No analytics, no CDN fonts, no phone-home.
- Unlock only works with a password **you already know**. Bindery does not break encryption.

## Windows: run it as an app (no Python)

1. Download the `Bindery-windows.zip` from Releases (or a zip someone built with `build-exe.bat`).
2. Unzip the **entire** folder. Keep `Bindery.exe` next to `_internal`.
3. Double-click `Bindery.exe`. Close the window to quit.

Windows may warn that the file is unsigned. Choose **More info → Run anyway** only if you trust the sender.

## Windows: run from this repo

You need [Python 3.10+](https://www.python.org/downloads/) once.

```powershell
git clone https://github.com/xraghav/36xBindery.git
cd 36xBindery
.\run.bat
```

`run.bat` opens the desk in the browser at `http://127.0.0.1:8741`. Leave the console open while you work.

To pin a Start menu / Desktop icon that opens **its own window**:

```powershell
.\install.bat
```

## What it does

- Merge PDFs
- Split / demerge (ranges, every N pages, or one file per page)
- Unlock / lock (AES-256)
- Rotate, drop, or reorder pages
- Compress, including an optional size ceiling
- Watermark
- Extract text or embedded images
- Edit title / author / keywords

## Build a zip to share inside the firm

```powershell
.\build-exe.bat
```

That writes `dist\Bindery-windows.zip`. Recipients do not need Python.

While you are changing the code, use `run.bat` or `install.bat` — not an old `.exe`. Rebuild the zip when you want a new snapshot for others.

## 36XFINANCE

[36xfinance.com](https://www.36xfinance.com/) — financial clarity through thoughtful guidance.
