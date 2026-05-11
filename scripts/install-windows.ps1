[CmdletBinding()]
param(
    [ValidateSet("claude-code", "codex", "both")]
    [string]$Target = "both"
)

$ErrorActionPreference = "Stop"

$Source = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$HomeDir = [Environment]::GetFolderPath("UserProfile")
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

function Get-PluginVersion {
    $manifest = Join-Path $Source ".codex-plugin\plugin.json"
    return ((Get-Content -Raw -LiteralPath $manifest) | ConvertFrom-Json).version
}

function Get-FullPath {
    param([Parameter(Mandatory)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Assert-Under {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)][string]$Label
    )
    $full = Get-FullPath $Path
    $rootFull = (Get-FullPath $Root).TrimEnd("\") + "\"
    if (-not $full.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label path is outside expected root. Path=$full Root=$rootFull"
    }
}

function Copy-PluginSource {
    param(
        [Parameter(Mandatory)][string]$Destination
    )

    $excludedDirs = @("__pycache__", ".git", ".pytest_cache", ".mypy_cache", "node_modules")
    $excludedSuffixes = @(".pyc", ".pyo", ".DS_Store", ".swp", ".swo")

    foreach ($item in Get-ChildItem -Force -LiteralPath $Source) {
        $name = $item.Name
        if ($item.PSIsContainer -and ($excludedDirs -contains $name -or $name.StartsWith(".test-"))) {
            continue
        }
        $skipFile = $false
        if (-not $item.PSIsContainer) {
            foreach ($suffix in $excludedSuffixes) {
                if ($name.EndsWith($suffix, [System.StringComparison]::OrdinalIgnoreCase)) {
                    $skipFile = $true
                    break
                }
            }
        }
        if ($skipFile) {
            continue
        }
        Copy-Item -LiteralPath $item.FullName -Destination $Destination -Recurse -Force
    }
}

function Remove-ExcludedInstallState {
    param(
        [Parameter(Mandatory)][string]$RootPath
    )

    $excludedNames = @("__pycache__", ".pytest_cache", ".mypy_cache", "node_modules")
    foreach ($item in Get-ChildItem -Force -LiteralPath $RootPath -ErrorAction SilentlyContinue) {
        if ($item.PSIsContainer -and ($excludedNames -contains $item.Name -or $item.Name.StartsWith(".test-"))) {
            Remove-Item -LiteralPath $item.FullName -Recurse -Force -ErrorAction Stop
        }
    }
}

function Copy-PluginTree {
    param(
        [Parameter(Mandatory)][string]$Destination,
        [Parameter(Mandatory)][string]$AllowedRoot,
        [Parameter(Mandatory)][string]$BackupRoot,
        [ValidateSet("claude-code", "codex")]
        [Parameter(Mandatory)][string]$Runtime
    )

    $destFull = Get-FullPath $Destination
    Assert-Under -Path $destFull -Root $AllowedRoot -Label "$Runtime install"

    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destFull) | Out-Null
    New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

    if (Test-Path -LiteralPath $destFull) {
        Copy-Item -LiteralPath $destFull -Destination (Join-Path $BackupRoot "ultraprompt") -Recurse -Force
        Remove-Item -LiteralPath $destFull -Recurse -Force
    }

    New-Item -ItemType Directory -Force -Path $destFull | Out-Null
    Remove-ExcludedInstallState -RootPath $destFull
    Copy-PluginSource -Destination $destFull
    Remove-ExcludedInstallState -RootPath $destFull

    Copy-Item -LiteralPath (Join-Path $destFull ".mcp.windows.json") -Destination (Join-Path $destFull ".mcp.json") -Force
    Copy-Item -LiteralPath (Join-Path $destFull ".codex.mcp.windows.json") -Destination (Join-Path $destFull ".codex.mcp.json") -Force
    Copy-Item -LiteralPath (Join-Path $destFull "hooks\hooks.windows.json") -Destination (Join-Path $destFull "hooks\hooks.json") -Force

    return $destFull
}

function Invoke-PluginValidation {
    param(
        [Parameter(Mandatory)][string]$PluginPath,
        [ValidateSet("claude-code", "codex")]
        [Parameter(Mandatory)][string]$Runtime
    )
    Push-Location -LiteralPath $PluginPath
    try {
        & py -3 .\scripts\build-skill-index.py
        if ($LASTEXITCODE -ne 0) { throw "build-skill-index.py failed for $Runtime" }
        & py -3 .\scripts\build-catalog-metadata.py
        if ($LASTEXITCODE -ne 0) { throw "build-catalog-metadata.py failed for $Runtime" }
        & py -3 .\scripts\build-capability-graph.py
        if ($LASTEXITCODE -ne 0) { throw "build-capability-graph.py failed for $Runtime" }
        & py -3 .\scripts\audit-manifest-schemas.py --runtime $Runtime
        if ($LASTEXITCODE -ne 0) { throw "audit-manifest-schemas.py failed for $Runtime" }
        & py -3 .\scripts\validate-plugin.py
        if ($LASTEXITCODE -ne 0) { throw "validate-plugin.py failed for $Runtime" }
    } finally {
        Pop-Location
    }
}

function Write-InstallManifest {
    param(
        [Parameter(Mandatory)][string]$PluginPath,
        [Parameter(Mandatory)][string]$BackupRoot,
        [Parameter(Mandatory)][string]$Version
    )
    & py -3 (Join-Path $PluginPath "scripts\install-manifest.py") write $PluginPath --backup-root $BackupRoot --plugin-version $Version | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Install manifest written"
    } else {
        Write-Host "Install manifest skipped (non-blocking)"
    }
}

function Ensure-ClaudeMarketplace {
    $marketRoot = Join-Path $HomeDir ".claude\plugins\marketplaces\ultraprompt-local"
    $manifestDir = Join-Path $marketRoot ".claude-plugin"
    $marketplace = Join-Path $manifestDir "marketplace.json"
    New-Item -ItemType Directory -Force -Path $manifestDir | Out-Null

    if (-not (Test-Path -LiteralPath $marketplace)) {
        $json = [ordered]@{
            name = "ultraprompt-local"
            owner = @{ name = "Ultraprompt Toolkit" }
            metadata = @{ description = "Local marketplace for the Ultraprompt Claude Code plugin." }
            plugins = @(
                [ordered]@{
                    name = "ultraprompt"
                    description = "Senior-maintainer Claude Code and Codex plugin."
                    source = "./plugins/ultraprompt"
                    category = "productivity"
                }
            )
        } | ConvertTo-Json -Depth 10
        Set-Content -LiteralPath $marketplace -Value $json -Encoding UTF8
    }

    return $marketRoot
}

function Ensure-CodexMarketplace {
    $agentsDir = Join-Path $HomeDir ".agents\plugins"
    $marketplace = Join-Path $agentsDir "marketplace.json"
    New-Item -ItemType Directory -Force -Path $agentsDir | Out-Null

    if (Test-Path -LiteralPath $marketplace) {
        $data = (Get-Content -Raw -LiteralPath $marketplace) | ConvertFrom-Json
    } else {
        $data = [pscustomobject]@{
            name = "ultraprompt-local"
            interface = [pscustomobject]@{ displayName = "Ultraprompt Local" }
            plugins = @()
        }
    }

    $plugins = @($data.plugins)
    $existing = $plugins | Where-Object { $_.name -eq "ultraprompt" } | Select-Object -First 1
    if ($null -eq $existing) {
        $plugins += [pscustomobject]@{
            name = "ultraprompt"
            source = [pscustomobject]@{ source = "local"; path = "./plugins/ultraprompt" }
            policy = [pscustomobject]@{ installation = "INSTALLED_BY_DEFAULT"; authentication = "ON_INSTALL" }
            category = "Productivity"
        }
    } else {
        $existing.source = [pscustomobject]@{ source = "local"; path = "./plugins/ultraprompt" }
        if ($null -eq $existing.policy) {
            $existing | Add-Member -NotePropertyName policy -NotePropertyValue ([pscustomobject]@{ installation = "INSTALLED_BY_DEFAULT"; authentication = "ON_INSTALL" })
        }
        if ($null -eq $existing.category) {
            $existing | Add-Member -NotePropertyName category -NotePropertyValue "Productivity"
        }
    }
    $data.plugins = $plugins
    $data | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $marketplace -Encoding UTF8
}

function Update-CodexConfig {
    $config = Join-Path $HomeDir ".codex\config.toml"
    if (-not (Test-Path -LiteralPath $config)) { return }

    $text = Get-Content -Raw -LiteralPath $config
    if ($text -notmatch '\[plugins\."ultraprompt@ultraprompt-local"\]') {
        $text = $text.TrimEnd() + "`r`n`r`n[plugins.`"ultraprompt@ultraprompt-local`"]`r`nenabled = true`r`n"
    }
    if ($text -notmatch '\[marketplaces\.ultraprompt-local\]') {
        $source = $HomeDir.Replace("\", "\\")
        $text = $text.TrimEnd() + "`r`n`r`n[marketplaces.ultraprompt-local]`r`nlast_updated = `"2024-01-01T00:00:00Z`"`r`nsource_type = `"local`"`r`nsource = '$source'`r`n"
    } else {
        $text = [regex]::Replace(
            $text,
            '(?s)(\[marketplaces\.ultraprompt-local\](?:(?!\r?\n\[).)*?last_updated\s*=\s*)"[^"]+"',
            '${1}"2024-01-01T00:00:00Z"'
        )
    }
    Set-Content -LiteralPath $config -Value $text -Encoding UTF8
}

function Populate-CodexCache {
    param(
        [Parameter(Mandatory)][string]$PluginPath,
        [Parameter(Mandatory)][string]$BackupRoot,
        [Parameter(Mandatory)][string]$Version
    )
    $cacheRoot = Join-Path $HomeDir ".codex\plugins\cache\ultraprompt-local\ultraprompt"
    Assert-Under -Path $cacheRoot -Root (Join-Path $HomeDir ".codex\plugins\cache") -Label "Codex cache"

    $versionCache = Join-Path $cacheRoot $Version
    if (Test-Path -LiteralPath $versionCache) {
        $cacheBackup = Join-Path $BackupRoot "cache-stale"
        New-Item -ItemType Directory -Force -Path $cacheBackup | Out-Null
        Copy-Item -LiteralPath $versionCache -Destination (Join-Path $cacheBackup $Version) -Recurse -Force
        try {
            foreach ($child in Get-ChildItem -Force -LiteralPath $versionCache) {
                Remove-Item -LiteralPath $child.FullName -Recurse -Force -ErrorAction Stop
            }
        } catch {
            Write-Host "Codex cache is in use; overlaying patched files in place."
        }
    }

    New-Item -ItemType Directory -Force -Path $versionCache | Out-Null
    foreach ($item in Get-ChildItem -Force -LiteralPath $PluginPath) {
        Copy-Item -LiteralPath $item.FullName -Destination $versionCache -Recurse -Force
    }
    Remove-ExcludedInstallState -RootPath $versionCache
    Write-Host "Populated Codex cache: $versionCache"
}

function Install-ClaudeCode {
    $version = Get-PluginVersion
    $marketRoot = Ensure-ClaudeMarketplace
    $targetPath = Join-Path $marketRoot "plugins\ultraprompt"
    $backupRoot = Join-Path $HomeDir ".claude\backups\ultraprompt-pre-windows-$Timestamp"
    Write-Host "Installing Claude Code plugin to $targetPath"
    $installed = Copy-PluginTree -Destination $targetPath -AllowedRoot $marketRoot -BackupRoot $backupRoot -Runtime "claude-code"
    Invoke-PluginValidation -PluginPath $installed -Runtime "claude-code"
    Remove-ExcludedInstallState -RootPath $installed
    Write-InstallManifest -PluginPath $installed -BackupRoot $backupRoot -Version $version
}

function Install-Codex {
    $version = Get-PluginVersion
    Ensure-CodexMarketplace
    Update-CodexConfig
    $targetPath = Join-Path $HomeDir "plugins\ultraprompt"
    $backupRoot = Join-Path $HomeDir ".codex\local-marketplace\backups\ultraprompt-pre-windows-$Timestamp"
    Write-Host "Installing Codex plugin source to $targetPath"
    $installed = Copy-PluginTree -Destination $targetPath -AllowedRoot (Join-Path $HomeDir "plugins") -BackupRoot $backupRoot -Runtime "codex"
    Invoke-PluginValidation -PluginPath $installed -Runtime "codex"
    Remove-ExcludedInstallState -RootPath $installed
    Populate-CodexCache -PluginPath $installed -BackupRoot $backupRoot -Version $version
    Write-InstallManifest -PluginPath $installed -BackupRoot $backupRoot -Version $version
}

switch ($Target) {
    "claude-code" { Install-ClaudeCode }
    "codex" { Install-Codex }
    "both" {
        Install-ClaudeCode
        Write-Host ""
        Install-Codex
    }
}

Write-Host ""
Write-Host "Ultraprompt Windows install complete. Restart Claude Code and fully restart Codex."
