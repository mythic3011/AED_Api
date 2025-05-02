# PowerShell script to rebuild Docker containers

Write-Host "Stopping containers..." -ForegroundColor Cyan
docker-compose down

Write-Host "Converting shell scripts to UNIX format..." -ForegroundColor Cyan
# Using PowerShell to convert line endings
Get-ChildItem -Path . -Filter "*.sh" | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    if ($content) {
        $unixContent = $content -replace "`r`n", "`n"
        [System.IO.File]::WriteAllText($_.FullName, $unixContent)
        Write-Host "Converted: $($_.Name)" -ForegroundColor Green
    }
}

Write-Host "Rebuilding containers with no cache..." -ForegroundColor Cyan
docker-compose build --no-cache

Write-Host "Starting containers..." -ForegroundColor Cyan
docker-compose up -d

Write-Host "Tailing logs from aed-api container..." -ForegroundColor Cyan
docker-compose logs -f api
