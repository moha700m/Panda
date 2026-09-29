$ErrorActionPreference = 'Stop'

python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed with exit code $LASTEXITCODE" }
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed with exit code $LASTEXITCODE" }

$vendor = Join-Path $PWD 'vendor'
New-Item -ItemType Directory -Force $vendor | Out-Null
Invoke-WebRequest -Uri "https://github.com/yannbouteiller/vgamepad/archive/refs/tags/v0.1.0.zip" -OutFile "$vendor\vgamepad.zip"
Expand-Archive -Path "$vendor\vgamepad.zip" -DestinationPath "$vendor\src" -Force
Copy-Item -Path "$vendor\src\vgamepad-0.1.0\vgamepad" -Destination ".\vgamepad" -Recurse -Force

if (!(Test-Path ".\vgamepad\win\vigem\client\x64\ViGEmClient.dll")) {
  throw "ViGEmClient.dll missing from vgamepad source"
}

python -m compileall -q panda tests main.py app.py
if ($LASTEXITCODE -ne 0) { throw "Python source compilation failed with exit code $LASTEXITCODE" }
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Python tests failed with exit code $LASTEXITCODE" }
python -m compileall -q vgamepad
if ($LASTEXITCODE -ne 0) { throw "Vendored vgamepad compilation failed with exit code $LASTEXITCODE" }

python -m PyInstaller --noconfirm --clean --onefile --windowed --name PandaTrainingStandalone `
  --hidden-import PySide6.QtCore --hidden-import PySide6.QtGui --hidden-import PySide6.QtWidgets `
  --hidden-import shiboken6 `
  --add-binary "vgamepad\win\vigem\client\x64\ViGEmClient.dll;vgamepad\win\vigem\client\x64" `
  main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$hash = (Get-FileHash -Algorithm SHA256 .\dist\PandaTrainingStandalone.exe).Hash
"PandaTrainingStandalone.exe  SHA256=$hash" | Out-File -Encoding ascii .\dist\SHA256.txt
Write-Host "Built dist\PandaTrainingStandalone.exe"
Write-Host "SHA256=$hash"
