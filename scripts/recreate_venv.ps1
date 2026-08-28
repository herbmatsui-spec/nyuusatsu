# venv 再作成スクリプト (PowerShell)
# 破損した仮想環境を安全に作り直す。
# 実行: pwsh scripts/recreate_venv.ps1

$ErrorActionPreference = "Stop"

$venvName = ".venv"
$tmpName  = ".venv_new"
$oldName  = ".venv_old"

Write-Host "1) 新しい仮想環境を作成: $tmpName"
if (Test-Path $tmpName) { Remove-Item -Recurse -Force $tmpName }
python -m venv $tmpName

Write-Host "2) 依存関係をインストール"
& "$tmpName/Scripts/pip.exe" install --upgrade pip
& "$tmpName/Scripts/pip.exe" install -r requirements.txt

Write-Host "3) 古い環境を置換"
if (Test-Path $venvName) {
    if (Test-Path $oldName) { Remove-Item -Recurse -Force $oldName }
    Rename-Item -Path $venvName -NewName $oldName
}
Rename-Item -Path $tmpName -NewName $venvName
if (Test-Path $oldName) { Remove-Item -Recurse -Force $oldName }

Write-Host "venv 再作成完了"
