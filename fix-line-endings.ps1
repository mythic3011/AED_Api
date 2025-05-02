# Script to convert shell scripts from Windows (CRLF) to Unix (LF) line endings
$files = @(
    "init-postgis.sh",
    "universal_start.sh",
    "init-postgres.sh"
)

foreach ($file in $files) {
    Write-Host "Converting $file to Unix line endings..."
    $content = Get-Content -Path $file -Raw
    $unixContent = $content -replace "`r`n", "`n"
    [System.IO.File]::WriteAllText($file, $unixContent)
}

Write-Host "All files converted successfully!"
