```powershell
$projectRoot = (Resolve-Path .).Path
$outItem = Get-Item graphify-out -Force -ErrorAction SilentlyContinue
if ($outItem -and (($outItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
    throw "Refusing to use reparse-point graphify-out"
}
if ($outItem -and -not $outItem.PSIsContainer) {
    throw "graphify-out exists but is not a directory"
}
if (-not $outItem) { New-Item -ItemType Directory -Path graphify-out | Out-Null }
$resolvedOut = (Resolve-Path graphify-out).Path
$expectedOut = [IO.Path]::GetFullPath((Join-Path $projectRoot 'graphify-out'))
if ([IO.Path]::GetFullPath($resolvedOut) -ne $expectedOut) {
    throw "graphify-out resolves outside the project root"
}
$pythonMarker = Get-Item graphify-out\.graphify_python -Force -ErrorAction SilentlyContinue
if ($pythonMarker -and (($pythonMarker.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
    throw "Refusing to read a reparse-point Python interpreter marker"
}
if (-not (Test-Path graphify-out\.graphify_python)) {
    $GRAPHIFY_PYTHON = $null
    $graphifyCmd = Get-Command graphify -ErrorAction SilentlyContinue
    if ($graphifyCmd) {
        # The interpreter that owns the graphify entry point sits next to it
        # (<env>\Scripts\python.exe for uv tool, pipx, and venv installs).
        $py = Join-Path (Split-Path $graphifyCmd.Source) "python.exe"
        if (Test-Path $py) { $GRAPHIFY_PYTHON = $py }
    }
    if (-not $GRAPHIFY_PYTHON) { $GRAPHIFY_PYTHON = "python" }
    New-Item -ItemType Directory -Force -Path graphify-out | Out-Null
    & $GRAPHIFY_PYTHON -c "import sys; open('graphify-out/.graphify_python', 'w', encoding='utf-8').write(sys.executable)"
}
```
