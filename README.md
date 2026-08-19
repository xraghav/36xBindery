# Bindery — private PDF desk

Local-only PDF tools for this machine. Bindery listens on **127.0.0.1** only. It does not call the internet, does not create accounts, and does not upload your files.

Windows users who just want the app: unzip `Bindery-windows.zip` and double-click **Bindery.exe**. Python is not required.

## What it does

- Merge several PDFs
- Split / demerge (page ranges, every N pages, or one file per page)
- Unlock a PDF when you already know the password
- Lock a copy with AES-256
- Rotate, drop, or reorder pages
- Compress
- Watermark
- Extract text or embedded images
- Edit title / author / keywords

The original files are never overwritten. You always download a new copy.

## Run from source (Windows)

You need [Python 3.10+](https://www.python.org/downloads/) once. Then double-click `run.bat`.

The browser opens `http://127.0.0.1:8741`. Leave the console window open while you work. Close it to stop Bindery.

```powershell
git clone https://github.com/REPLACE_ME/bindery.git
cd bindery
.\run.bat
```

## Build the Windows .exe

On a Windows PC with Python:

```powershell
.\run.bat
# stop it with Ctrl+C after it has installed packages, then:
.\build-exe.bat
```

That writes:

- `dist\Bindery\Bindery.exe` — the app
- `dist\Bindery-windows.zip` — the folder you can send to people

Recipients unzip anywhere and run `Bindery.exe`. Keep the whole unzipped folder together (`_internal` must sit next to the exe).

Windows SmartScreen may say the file is unsigned. That is expected until someone signs the build with a code-signing certificate. Recipients can choose **More info → Run anyway** if they trust you.

## Privacy

- Bound to localhost. Other computers on the network cannot reach it.
- Processing happens in a `.sessions` folder next to the app, then you download the result.
- Sessions older than four hours are discarded on the next request.
- No analytics, CDNs, or online fonts — the interface is fully local.

Unlock only works with a password you already have. Bindery will not try to break unknown encryption.

## License

MIT. See `LICENSE`.
