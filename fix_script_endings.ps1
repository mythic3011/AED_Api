#!/bin/bash

echo "Converting universal_start.sh to Unix format..."
Get-Content -Path .\universal_start.sh -Raw | % { $_.Replace("`r`n", "`n") } | Set-Content -Path .\universal_start.sh.unix -NoNewline
Move-Item -Force -Path .\universal_start.sh.unix -Destination .\universal_start.sh

echo "Converting api_health_check.sh to Unix format..."
if (Test-Path -Path .\api_health_check.sh) {
    Get-Content -Path .\api_health_check.sh -Raw | % { $_.Replace("`r`n", "`n") } | Set-Content -Path .\api_health_check.sh.unix -NoNewline
    Move-Item -Force -Path .\api_health_check.sh.unix -Destination .\api_health_check.sh
}

echo "Done!"
