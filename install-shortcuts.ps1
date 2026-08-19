$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyw = Join-Path $root ".venv\Scripts\pythonw.exe"
$app = Join-Path $root "desktop.py"
$ico = Join-Path $root "static\bindery.ico"
$ws = New-Object -ComObject WScript.Shell
$targets = @(
  (Join-Path $env:USERPROFILE "Desktop\36x Bindery.lnk"),
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\36x Bindery.lnk")
)
foreach ($path in $targets) {
    $dir = Split-Path -Parent $path
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
    $s = $ws.CreateShortcut($path)
    $s.TargetPath = $pyw
    $s.Arguments = "`"$app`""
    $s.WorkingDirectory = $root
    $s.WindowStyle = 7
    if (Test-Path $ico) { $s.IconLocation = $ico }
    $s.Description = "36x Bindery — 36XFINANCE private PDF desk"
    $s.Save()
    Write-Output $path
}
