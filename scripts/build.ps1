param([string]$Version = '0.1.0', [switch]$SkipInstaller, [string]$IsccPath)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $python = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Create .venv and install requirements-build.txt first.' }
    & $python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    & $python 'scripts\make_icon.py'
    & $python -m PyInstaller --noconfirm --clean --onedir --windowed --name CodexSwitch --icon assets/codex-switch.ico --add-data 'assets;assets' --paths src app_gui.py
    if ($LASTEXITCODE -ne 0) { throw 'GUI build failed.' }
    & $python -m PyInstaller --noconfirm --clean --onefile --console --name codex-switch --icon assets/codex-switch.ico --paths src app_cli.py
    if ($LASTEXITCODE -ne 0) { throw 'CLI build failed.' }
    Copy-Item -LiteralPath 'dist\codex-switch.exe' -Destination 'dist\CodexSwitch\codex-switch.exe' -Force
    Copy-Item -LiteralPath 'README.md','README.en.md','LICENSE','THIRD_PARTY_NOTICES.md' -Destination 'dist\CodexSwitch' -Force
    Copy-Item -LiteralPath 'docs' -Destination 'dist\CodexSwitch' -Recurse -Force
    & $python 'scripts\collect_licenses.py'
    if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
    & $python 'scripts\smoke.py' 'dist\CodexSwitch\codex-switch.exe'
    if ($LASTEXITCODE -ne 0) { throw 'Packaged CLI smoke failed.' }
    New-Item -ItemType Directory -Path 'release' -Force | Out-Null
    $zip = Join-Path $root "release\CodexSwitch-$Version-windows-x64-portable.zip"
    Compress-Archive -Path 'dist\CodexSwitch' -DestinationPath $zip -Force
    if (-not $SkipInstaller) {
        if (-not $IsccPath) {
            $IsccPath = @('C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
                          'C:\Program Files\Inno Setup 7\ISCC.exe',
                          (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'),
                          (Join-Path $root '.tools\InnoSetup\ISCC.exe')) |
                Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        }
        if (-not $IsccPath) { throw 'Inno Setup compiler not found. Pass -IsccPath or use -SkipInstaller.' }
        & $IsccPath "/DAppVersion=$Version" 'installer\CodexSwitch.iss'
        if ($LASTEXITCODE -ne 0) { throw 'Installer build failed.' }
    }
    $hashes = Get-ChildItem -LiteralPath 'release' -File | Where-Object { $_.Extension -in '.exe','.zip' } |
        Get-FileHash -Algorithm SHA256 | ForEach-Object { $_.Hash.ToLowerInvariant() + '  ' + (Split-Path -Leaf $_.Path) }
    [IO.File]::WriteAllLines((Join-Path $root 'release\SHA256SUMS.txt'), $hashes, (New-Object Text.UTF8Encoding($false)))
} finally { Pop-Location }
