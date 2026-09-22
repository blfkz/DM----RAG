param([string]$Src, [string]$Dst)
$ErrorActionPreference = "Stop"
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($Src, $false, $true)
    # 格式 0 = wdFormatDocument (Word 97-2003 .doc)
    $doc.SaveAs([ref]$Dst, [ref]0)
    $doc.Close($false)
    $word.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
    Write-Output "DOC OK"
} catch {
    Write-Output ("FAIL: " + $_.Exception.Message)
    exit 1
}
