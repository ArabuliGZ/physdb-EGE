# Combine the 2024 series-1 source, answer key and worked criteria in Word.
# Original DOC files and the converted DOCX inputs remain untouched.
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$inputRoot = Join-Path $projectRoot 'tmp\normalized-doc\2024 - 1'
$outputRoot = Join-Path $projectRoot 'Материалы\ЕГЭ от Демидовой\2024 - 1'
$qaRoot = Join-Path $projectRoot 'tmp\merged_qa'
New-Item -ItemType Directory -Path $qaRoot -Force | Out-Null
$word = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    for ($number = 1; $number -le 4; $number++) {
        $source = Join-Path $inputRoot "$number.docx"
        $key = Join-Path $inputRoot "${number}_ключ.docx"
        $criteria = Join-Path $inputRoot "${number}_крит.docx"
        $output = Join-Path $outputRoot "${number}_полный.docx"
        foreach ($path in @($source, $key, $criteria)) {
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
                throw "Missing merge input: $path"
            }
        }
        $document = $null
        try {
            $document = $word.Documents.Open($source, $false, $false)
            $document.SaveAs2($output, 16)
            $document.Activate()
            foreach ($appendix in @($key, $criteria)) {
                $selection = $word.Selection
                $selection.EndKey(6) | Out-Null # wdStory
                $selection.InsertBreak(7)     # wdPageBreak
                $selection.InsertFile($appendix)
            }
            $document.Save()
            $document.ExportAsFixedFormat((Join-Path $qaRoot "$number.pdf"), 17) # wdExportFormatPDF
            Write-Output "merged: $output"
        }
        finally {
            if ($document) { $document.Close($false) }
        }
    }
}
finally {
    if ($word) { $word.Quit() }
}
