param([string]$Src, [string]$Dst)
$ErrorActionPreference = "Stop"
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($Src, $false, $true)
    $doc.SaveAs([ref]$Dst, [ref]17)
    $doc.Close($false)
    $word.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
    Write-Output "PDF OK"
} catch {
    Write-Output ("FAIL: " + $_.Exception.Message)
    exit 1
}
