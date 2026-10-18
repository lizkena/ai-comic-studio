$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $releaseCompiler = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    & $releaseCompiler /nologo /target:winexe /platform:x64 /out:Launcher.exe /win32icon:studio.ico /win32manifest:launcher.manifest /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll /reference:Microsoft.Web.WebView2.Core.dll /reference:Microsoft.Web.WebView2.WinForms.dll launcher.cs
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
    Move-Item -LiteralPath './Launcher.exe' -Destination './AI漫剧工作台.exe' -Force
} finally { Pop-Location }
