<#
  Baut MarkMyWords.exe (Standalone-GUI ohne Konsole) nach dist\.

  .\build.ps1            Basis-Build (ohne PDF-Import)
  .\build.ps1 -WithCli   baut zusätzlich mdconv.exe (Konsole)
  .\build.ps1 -WithPdf   inkl. Docling für PDF -> MD (experimentell, sehr groß, als Ordner-Build)
#>
param([switch]$WithPdf, [switch]$WithCli)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$extras = @()
if ($WithPdf) { $extras += @("--extra", "pdf") }
uv sync @extras --group dev
if ($LASTEXITCODE) { throw "uv sync fehlgeschlagen" }

$iconPath = Join-Path $PSScriptRoot "assets\MarkMyWords.ico"
if (-not (Test-Path $iconPath)) {
    throw "Icon fehlt: $iconPath"
}

# Pandoc aus pypandoc-binary nach vendor\bin kopieren
New-Item -ItemType Directory -Force vendor\bin | Out-Null
$pandoc = uv run --no-sync python -c "from pathlib import Path; import pypandoc; p = Path(pypandoc.get_pandoc_path()); print(p if p.is_file() else p.with_suffix('.exe'))"
Copy-Item $pandoc vendor\bin\pandoc.exe -Force

if (-not (Test-Path vendor\bin\typst.exe)) {
    Write-Warning "vendor\bin\typst.exe fehlt - MD -> PDF funktioniert in der EXE dann nicht."
    Write-Warning "Download: https://github.com/typst/typst/releases (typst-x86_64-pc-windows-msvc.zip)"
}

$bins = @()
Get-ChildItem vendor\bin\*.exe | ForEach-Object { $bins += @("--add-binary", "$($_.FullName);bin") }

$common = @("--noconfirm", "--clean", "--paths", "src", "--exclude-module", "pypandoc") + $bins
$mode = "--onefile"
if ($WithPdf) {
    # Torch & Modelle: Ordner-Build startet deutlich schneller als onefile
    $mode = "--onedir"
    $common += @("--collect-all", "docling", "--collect-all", "docling_core",
                 "--collect-all", "docling_parse", "--collect-all", "docling_ibm_models")
}

uv run --no-sync pyinstaller @common $mode --windowed `
    --name MarkMyWords `
    --icon $iconPath `
    --add-data "${iconPath};assets" `
    packaging\mdconv_gui.py
if ($LASTEXITCODE) { throw "Build MarkMyWords fehlgeschlagen" }

if ($WithCli) {
    uv run --no-sync pyinstaller @common $mode --name mdconv packaging\mdconv_cli.py
    if ($LASTEXITCODE) { throw "Build mdconv fehlgeschlagen" }
}

$targetPath = if ($WithPdf) { "dist\MarkMyWords\MarkMyWords.exe" } else { "dist\MarkMyWords.exe" }
Write-Host "`nFertig: $targetPath" -ForegroundColor Green
