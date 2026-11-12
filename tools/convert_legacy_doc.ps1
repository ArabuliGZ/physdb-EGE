# Convert source .doc files to temporary .docx copies for OOXML inspection.
# The original documents are opened read-only and are never saved in place.
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$sourceRoot = (Resolve-Path -LiteralPath (Join-Path $projectRoot 'Материалы\ЕГЭ от Демидовой')).Path
$tempRoot = Join-Path $projectRoot 'tmp\normalized-doc'
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
$folders = @('2024 - 1', '2025 - 1', '2025 - 2')
$word = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    foreach ($folder in $folders) {
        $sourceFolder = Join-Path $sourceRoot $folder
        $targetFolder = Join-Path $tempRoot $folder
        New-Item -ItemType Directory -Path $targetFolder -Force | Out-Null
        foreach ($file in (Get-ChildItem -LiteralPath $sourceFolder -Filter '*.doc' -File | Sort-Object Name)) {
            $target = Join-Path $targetFolder ($file.BaseName + '.docx')
            if (Test-Path -LiteralPath $target) {
                if ((Get-Item -LiteralPath $target).LastWriteTimeUtc -ge $file.LastWriteTimeUtc) {
                    Write-Output "cached: $folder/$($file.Name)"
                    continue
                }
            }
            $document = $null
            try {
                $document = $word.Documents.Open($file.FullName, $false, $true)
                $document.SaveAs2($target, 16)
                Write-Output "converted: $folder/$($file.Name)"
            }
            finally {
                if ($document) { $document.Close($false) }
            }
        }
    }
}
finally {
    if ($word) { $word.Quit() }
}
