# Registers a Windows scheduled task that runs the PS5 stock check every 5 minutes
# while you're logged in. Re-run this script to update the task.
# To remove it:  Unregister-ScheduledTask -TaskName "PS5 Stock Watch" -Confirm:$false

$ErrorActionPreference = "Stop"
$taskName = "PS5 Stock Watch"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $here "ps5_watch.py"

# pythonw.exe runs Python without opening a console window
$python = (Get-Command python).Source
$pythonw = Join-Path (Split-Path $python) "pythonw.exe"
if (-not (Test-Path $pythonw)) { throw "pythonw.exe not found next to $python" }

$action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`"" -WorkingDirectory $here
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Checks Canadian retailers for PS5 stock and sends an ntfy alert." -Force | Out-Null

Write-Host "Scheduled task '$taskName' installed: runs every 5 minutes using $pythonw"
