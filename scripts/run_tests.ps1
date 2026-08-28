# GEPSクローラー テスト実行スクリプト
# 使用法: powershell -ExecutionPolicy Bypass -File "i:\入札システム\scripts\run_tests.ps1"
#
# I:ドライブを Cwd にするとプロセスがフリーズするため、
# C:ドライブから PYTHONPATH 経由でテストを実行する

$ProjectRoot = "i:\入札システム"
$SafeCwd = $env:USERPROFILE  # C:\Users\keide

Write-Host "=== GEPS Crawler Test Runner ===" -ForegroundColor Cyan
Write-Host "Project Root: $ProjectRoot"
Write-Host "Working Dir:  $SafeCwd"
Write-Host ""

# 環境変数設定
$env:PYTHONPATH = $ProjectRoot
$env:PYTHONUNBUFFERED = "1"

# テスト実行（引数があればそれを渡す、なければ全テスト）
$testArgs = $args
if ($testArgs.Count -eq 0) {
    $testArgs = @("$ProjectRoot\tests", "-v", "--no-cov")
}

Push-Location $SafeCwd
try {
    python -u -m pytest @testArgs
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

exit $exitCode
