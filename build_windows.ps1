$ErrorActionPreference = 'Stop'
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name PandaTrainingStandalone `
  --collect-all dxcam --collect-all vgamepad --collect-all cv2 `
  app.py
$hash = (Get-FileHash -Algorithm SHA256 .\dist\PandaTrainingStandalone.exe).Hash
"PandaTrainingStandalone.exe  SHA256=$hash" | Out-File -Encoding ascii .\dist\SHA256.txt
Write-Host "Built dist\PandaTrainingStandalone.exe"
