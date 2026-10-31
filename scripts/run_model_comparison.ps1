<#
Same-code, same-machine chat model comparison.

For each model, config/rag.yml's chat_model_name is set (nothing else changes),
online doctor must pass, then each dataset runs retrieval + QA + Agent through
evaluation.run into its own new directory, followed by report and export.
config/rag.yml is restored afterwards. Re-running with the same -Tag resumes:
evaluation.run keeps committed records and refuses changed inputs.

Scores still need semantic review (reviews.jsonl); report does not grade answers.

-Suite service runs the frozen service_v1 test set end to end (service toolset)
in each of -Modes via evaluation.service_run, then service_score. That set was
already used formally in S5, so these runs are seen-set reruns; the runner's
formal gate (--formal plus SERVICE_EVAL_FORMAL=1) is set only for this call.

  powershell -ExecutionPolicy Bypass -File scripts/run_model_comparison.ps1
  powershell -ExecutionPolicy Bypass -File scripts/run_model_comparison.ps1 -Ids V2K01,V2N01,V2A01 -Datasets holdout_v2 -RunRoot $env:TEMP\smoke
  powershell -ExecutionPolicy Bypass -File scripts/run_model_comparison.ps1 -Suite service
#>
param(
    [string[]]$Models = @('qwen3:4b', 'gemma4:12b'),
    [ValidateSet('qa', 'service')][string]$Suite = 'qa',
    [string[]]$Datasets = @('generalization_v1', 'holdout_v2'),
    [string[]]$Modes = @('react', 'plan'),
    [string]$Tag = (Get-Date -Format 'yyyyMMdd'),
    [string[]]$Ids = @(),
    [string]$RunRoot = 'evaluation/results',
    [int]$Timeout = 240
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root '.venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$ragPath = Join-Path $root 'config\rag.yml'
$original = [IO.File]::ReadAllBytes($ragPath)
$utf8 = New-Object Text.UTF8Encoding($false)
# Comma-joined values survive powershell -File, which passes arrays as one string.
$Ids = @($Ids | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$Modes = @($Modes | ForEach-Object { $_ -split ',' } | Where-Object { $_ })

function Invoke-Checked([string[]]$Arguments) {
    & $python -B @Arguments
    if ($LASTEXITCODE -ne 0) { throw "python $($Arguments -join ' ') exited $LASTEXITCODE" }
}

try {
    foreach ($model in $Models) {
        $text = $utf8.GetString($original)
        if ($text -notmatch '(?m)^chat_model_name\s*:') { throw 'config/rag.yml has no chat_model_name line' }
        [IO.File]::WriteAllText($ragPath, ($text -replace '(?m)^chat_model_name\s*:.*$', "chat_model_name : $model"), $utf8)
        Write-Host "=== $model : doctor ==="
        Invoke-Checked @('scripts/manage.py', 'doctor')
        $slug = $model -replace '[^A-Za-z0-9]+', '_'
        if ($Suite -eq 'service') {
            foreach ($mode in $Modes) {
                $run = Join-Path $RunRoot "model_cmp_${Tag}_service_test_${mode}_${slug}"
                $arguments = @('-m', 'evaluation.service_run', '--dataset', 'evaluation/service_v1/test.jsonl', '--formal',
                               '--run', $run, '--mode', $mode, '--timeout', $Timeout)
                if ($Ids.Count) { $arguments += @('--ids') + $Ids }
                Write-Host "=== $model : service $mode -> $run ==="
                $started = Get-Date
                $env:SERVICE_EVAL_FORMAL = '1'
                try { & $python -B @arguments } finally { Remove-Item Env:SERVICE_EVAL_FORMAL -ErrorAction SilentlyContinue }
                # Exit 1 only means some task did not finish ok; those stay in the denominator.
                if ($LASTEXITCODE -gt 1) { throw "service_run exited $LASTEXITCODE" }
                Invoke-Checked @('-m', 'evaluation.service_score', '--run', $run)
                Write-Host ("=== {0} : service {1} done in {2:N0} min ===" -f $model, $mode, ((Get-Date) - $started).TotalMinutes)
            }
            continue
        }
        foreach ($set in $Datasets) {
            $run = Join-Path $RunRoot "model_cmp_${Tag}_${set}_${slug}"
            $arguments = @('-m', 'evaluation.run', '--dataset', "evaluation/$set/cases.jsonl", '--run', $run,
                           '--stage', 'all', '--timeout', $Timeout)
            if ($Ids.Count) { $arguments += @('--ids') + $Ids }
            Write-Host "=== $model : $set -> $run ==="
            $started = Get-Date
            Invoke-Checked $arguments
            Invoke-Checked @('-m', 'evaluation.report', '--run', $run)
            Invoke-Checked @('-m', 'evaluation.export', '--run', $run)
            Write-Host ("=== {0} : {1} done in {2:N0} min ===" -f $model, $set, ((Get-Date) - $started).TotalMinutes)
        }
    }
}
finally {
    [IO.File]::WriteAllBytes($ragPath, $original)
    Write-Host 'config/rag.yml restored'
}
