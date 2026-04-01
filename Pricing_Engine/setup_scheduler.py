# -*- coding: utf-8 -*-
"""
setup_scheduler.py — Register NelsonRateImporter in Windows Task Scheduler
=========================================================================
Two triggers for weekend coverage:
  1. Mon 08:00 -> --days 3 (catches Sat+Sun emails)
  2. Tue-Fri every 2 hours 08:00-18:00 -> --days 1

Run once:  python setup_scheduler.py
Verify:    schtasks /query /tn NelsonRateImporter
Remove:    schtasks /delete /tn NelsonRateImporter /f
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import subprocess

TASK_NAME = "NelsonRateImporter"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RATE_IMPORTER = os.path.join(SCRIPT_DIR, "rate_importer.py")
PYTHON_EXE = sys.executable

# Task Scheduler XML — dual triggers for weekend coverage
TASK_XML = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Nelson Freight - Auto import pricing rates. Mon: --days 3 (weekend catch-up). Tue-Fri: --days 1 every 2 hours.</Description>
    <Author>Nelson</Author>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-01-05T08:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByWeek>
        <DaysOfWeek><Monday/></DaysOfWeek>
        <WeeksInterval>1</WeeksInterval>
      </ScheduleByWeek>
    </CalendarTrigger>
    <CalendarTrigger>
      <Repetition>
        <Interval>PT2H</Interval>
        <Duration>PT10H</Duration>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>2026-01-06T08:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByWeek>
        <DaysOfWeek><Tuesday/><Wednesday/><Thursday/><Friday/></DaysOfWeek>
        <WeeksInterval>1</WeeksInterval>
      </ScheduleByWeek>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <DisallowStartOnRemoteAppSession>false</DisallowStartOnRemoteAppSession>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{PYTHON_EXE}</Command>
      <Arguments>"{RATE_IMPORTER}" --days 1</Arguments>
      <WorkingDirectory>{SCRIPT_DIR}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""

# Separate Monday --days 3 task
TASK_NAME_MON = "NelsonRateImporter_Monday"
TASK_XML_MON = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Nelson Freight - Monday weekend catch-up import (--days 3)</Description>
    <Author>Nelson</Author>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-01-05T08:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByWeek>
        <DaysOfWeek><Monday/></DaysOfWeek>
        <WeeksInterval>1</WeeksInterval>
      </ScheduleByWeek>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{PYTHON_EXE}</Command>
      <Arguments>"{RATE_IMPORTER}" --days 3</Arguments>
      <WorkingDirectory>{SCRIPT_DIR}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def register_task(task_name, task_xml):
    """Register a single task from XML."""
    xml_path = os.path.join(SCRIPT_DIR, f"_{task_name}.xml")
    with open(xml_path, "w", encoding="utf-16") as f:
        f.write(task_xml)

    # Delete existing
    subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"],
                   capture_output=True, text=True)

    # Create
    result = subprocess.run(["schtasks", "/create", "/tn", task_name, "/xml", xml_path],
                           capture_output=True, text=True)

    try:
        os.remove(xml_path)
    except OSError:
        pass

    if result.returncode == 0:
        print(f"  ✅ '{task_name}' registered")
        return True
    else:
        print(f"  ❌ '{task_name}' failed: {result.stderr or result.stdout}")
        return False


def main():
    print(f"{'='*60}")
    print(f"  NELSON RATE IMPORTER — Task Scheduler Setup")
    print(f"{'='*60}")
    print(f"  Python:  {PYTHON_EXE}")
    print(f"  Script:  {RATE_IMPORTER}")
    print()

    if not os.path.exists(RATE_IMPORTER):
        print(f"❌ rate_importer.py not found: {RATE_IMPORTER}")
        sys.exit(1)

    print("Registering tasks:")
    print(f"  {TASK_NAME}: Tue-Fri every 2h 08:00-18:00 (--days 1)")
    ok1 = register_task(TASK_NAME, TASK_XML)

    print(f"  {TASK_NAME_MON}: Mon 08:00 (--days 3, weekend catch-up)")
    ok2 = register_task(TASK_NAME_MON, TASK_XML_MON)

    if ok1 and ok2:
        print(f"\n✅ Both tasks registered!")
        print(f"\nVerify:")
        print(f"  schtasks /query /tn {TASK_NAME}")
        print(f"  schtasks /query /tn {TASK_NAME_MON}")
        print(f"\nManual run:")
        print(f"  schtasks /run /tn {TASK_NAME}")
        print(f"\nRemove:")
        print(f"  schtasks /delete /tn {TASK_NAME} /f")
        print(f"  schtasks /delete /tn {TASK_NAME_MON} /f")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
