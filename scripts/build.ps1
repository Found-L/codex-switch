param([string]$Version = '0.8.4', [switch]$SkipInstaller, [string]$IsccPath)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$originalBuildPath = $env:PATH
Push-Location $root
try {
    $python = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Create .venv and install requirements-build.txt first.' }
    # Keep unrelated native toolchains on the developer PATH out of DLL discovery.
    $pythonBase = & $python -c 'import sys; print(sys.base_prefix)'
    $env:PATH = @((Split-Path -Parent $python), $pythonBase, (Join-Path $env:WINDIR 'System32'), $env:WINDIR) -join ';'
    & $python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    & $python 'scripts\make_icon.py'
    & $python -m PyInstaller --noconfirm --clean --onedir --windowed --name CodexSwitch --icon assets/codex-switch.ico --add-data 'assets;assets' --add-data 'ui;ui' --paths src app_gui.py
    if ($LASTEXITCODE -ne 0) { throw 'GUI build failed.' }
    & $python -m PyInstaller --noconfirm --clean --onefile --console --name codex-switch --icon assets/codex-switch.ico --exclude-module PySide6 --exclude-module tkinter --paths src app_cli.py
    if ($LASTEXITCODE -ne 0) { throw 'CLI build failed.' }
    Copy-Item -LiteralPath 'dist\codex-switch.exe' -Destination 'dist\CodexSwitch\codex-switch.exe' -Force
    Copy-Item -LiteralPath 'README.md','README.en.md','LICENSE','THIRD_PARTY_NOTICES.md' -Destination 'dist\CodexSwitch' -Force
    Copy-Item -LiteralPath 'docs' -Destination 'dist\CodexSwitch' -Recurse -Force
    & $python 'scripts\gui_smoke.py' 'dist\CodexSwitch\CodexSwitch.exe'
    if ($LASTEXITCODE -ne 0) { throw 'Packaged GUI startup failed.' }
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
    $hashes = Get-ChildItem -LiteralPath 'release' -File | Where-Object { $_.Name -like "CodexSwitch-$Version-*" -and $_.Extension -in '.exe','.zip' } |
        Get-FileHash -Algorithm SHA256 | ForEach-Object { $_.Hash.ToLowerInvariant() + '  ' + (Split-Path -Leaf $_.Path) }
    [IO.File]::WriteAllLines((Join-Path $root 'release\SHA256SUMS.txt'), $hashes, (New-Object Text.UTF8Encoding($false)))
} finally { $env:PATH = $originalBuildPath; Pop-Location }
