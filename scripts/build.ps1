$root = Split-Path $PSScriptRoot -Parent

Stop-Process -Name tonguepasta -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

Set-Location "$root\src"
python -m PyInstaller --onefile --noconsole `
    --hidden-import pynput.keyboard._win32 `
    --hidden-import pynput.mouse._win32 `
    --hidden-import corrector `
    --name tonguepasta `
    main.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Build complete: src\dist\tonguepasta.exe"
