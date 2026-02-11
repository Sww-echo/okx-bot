# Auto-fix Path Environment Variable Script
# Features:
# 1. Backup USER and MACHINE Path variables.
# 2. Removing corrupted paths (containing non-ASCII or 'Tencent' garbage).
# 3. Remove duplicates.
# 4. Bypasses the 2047 character GUI limit.

$BackupFile = "$PSScriptRoot\path_backup_$(Get-Date -Format 'yyyyMMdd-HHmmss').txt"

function Clean-Path($Scope) {
    Write-Host "Processing $Scope Environment Variable..." -ForegroundColor Cyan
    
    try {
        $regPath = if ($Scope -eq 'Machine') { 
            "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" 
        } else { 
            "HKCU:\Environment" 
        }
        
        # Get raw value
        $rawPath = (Get-ItemProperty -Path $regPath -Name Path).Path
        
        # Backup
        "[$Scope] $rawPath" | Out-File -FilePath $BackupFile -Append
        
        # Split
        $parts = $rawPath -split ';'
        $newParts = @()
        $seen = @{}
        
        foreach ($p in $parts) {
            # Skip empty
            if ([string]::IsNullOrWhiteSpace($p)) { continue }
            
            # 1. Remove Corrupted Paths (Tencent garbage or non-ASCII)
            # Match common garbage patterns
            if ($p -match 'Tencent' -and $p -match '[^\x00-\x7F]') {
                Write-Host "  [-] Removing corrupted path: $p" -ForegroundColor Red
                continue
            }
            if ($p -match 'web' -and $p -match '[^\x00-\x7F]') {
                Write-Host "  [-] Removing corrupted path: $p" -ForegroundColor Red
                continue
            }

            # 2. Deduplicate
            $key = $p.Trim().ToLower()
            if (-not $seen.ContainsKey($key)) {
                $seen[$key] = $true
                $newParts += $p
            }
        }
        
        # Join
        $newPath = $newParts -join ';'
        
        # Check changes
        if ($newPath -ne $rawPath) {
            [Environment]::SetEnvironmentVariable('Path', $newPath, $Scope)
            Write-Host "  [+] $Scope Path updated and saved!" -ForegroundColor Green
        } else {
            Write-Host "  [=] $Scope Path requires no changes." -ForegroundColor Yellow
        }
        
    } catch {
        Write-Host "  [!] Error processing $Scope : $_" -ForegroundColor Red
    }
}

Write-Host "Original Path will be backed up to: $BackupFile"

# Clean User Path
Clean-Path 'User'

# Clean Machine Path (Requires Admin)
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($isAdmin) {
    Clean-Path 'Machine'
} else {
    Write-Host "`n[WARNING] No Admin privileges detected. Only User Path processed." -ForegroundColor Yellow
    Write-Host "If the corrupted entry is in System Path, run this script as Administrator." -ForegroundColor Yellow
}

Write-Host "`nDone! Please RESTART VS Code." -ForegroundColor Cyan
Write-Host "Press Enter to exit..."
Read-Host
