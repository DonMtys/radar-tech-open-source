# Inicia o canal no logon e repete uma rodada a cada 30 minutos.
$projectDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$botExecutable = Join-Path $projectDirectory 'RadarTechBot.exe'
$logFile = Join-Path $projectDirectory 'news_channel.log'
$instanceMutex = New-Object System.Threading.Mutex($false, 'Local\RadarTechOpenSourceHourly')
$hasMutex = $false
$keepAwakeEnabled = $false

try {
    $hasMutex = $instanceMutex.WaitOne(0)
    if (-not $hasMutex) { return }
    Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
public static class RadarTechPower {
    [DllImport("kernel32.dll")]
    public static extern uint SetThreadExecutionState(uint flags);
}
'@ -ErrorAction Stop
    $keepAwakeEnabled = [RadarTechPower]::SetThreadExecutionState([uint32]2147483649) -ne 0
    Set-Location -LiteralPath $projectDirectory
    if ($keepAwakeEnabled) {
        Add-Content -LiteralPath $logFile -Value '[CANAL TECH] Suspensao automatica bloqueada enquanto o bot esta ativo.'
    } else {
        Add-Content -LiteralPath $logFile -Value '[CANAL TECH] Aviso: nao foi possivel bloquear a suspensao automatica.'
    }
    & $botExecutable --news-loop --news-interval-minutes 30 *>> $logFile
} finally {
    if ($keepAwakeEnabled) {
        [RadarTechPower]::SetThreadExecutionState([uint32]2147483648) | Out-Null
    }
    if ($hasMutex) { $instanceMutex.ReleaseMutex() }
    $instanceMutex.Dispose()
}
