"""Run long jobs one after another, after something else has finished, with a log (overnight runs).

Command line:
    rh queue jobs.txt --log run.log [--after-file other.log --after-text "finished"] [--after-pid 1234]
             [--wait-for-pattern "python.*train"] [--keep-awake]
        jobs.txt: one command per line (# comments allowed), run in order; a failure does not stop the next job.

Python:
    from research_helpers.jobqueue import run_queue
    run_queue(["python train.py --area a", "python report.py"], log="run.log", after_pid=1234, keep_awake=True)

Conditions are checked every minute: a process id that must have ended, a log file that must contain a text, and a
regular expression that no running process command line may match (e.g. other model runs). --keep-awake stops the
computer from sleeping while the queue runs (Windows: SetThreadExecutionState; elsewhere use caffeinate / systemd-inhibit).
Each job is logged with its start time, its output and its exit code; the log ends with "queue finished", which
another queue can wait for.
"""
import datetime, os, pathlib, re, shlex, subprocess, sys, time

__all__ = ["run_queue"]


def _alive(pid):
    try:
        if os.name == "nt":
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
            return str(pid) in out
        os.kill(pid, 0); return True
    except Exception:
        return False


def _processes():
    try:
        if os.name == "nt":
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  "Get-CimInstance Win32_Process | ForEach-Object { $_.CommandLine }"], capture_output=True, text=True).stdout
        else:
            out = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
        return [l for l in out.splitlines() if l.strip()]
    except Exception:
        return []


def _keep_awake(on):
    if os.name == "nt":
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001 if on else 0x80000000)


def run_queue(jobs, log, after_pid=None, after_file=None, after_text=None, wait_for_pattern=None, keep_awake=False, poll=60):
    log = pathlib.Path(log); log.parent.mkdir(parents=True, exist_ok=True)
    me = str(os.getpid())

    def write(s):
        with open(log, "a", encoding="utf-8") as f:
            f.write(s + "\n")
        print(s, flush=True)

    def busy():
        if after_pid and _alive(after_pid):
            return True
        if after_file and (not pathlib.Path(after_file).exists() or after_text not in pathlib.Path(after_file).read_text(errors="replace")):
            return True
        if wait_for_pattern and any(re.search(wait_for_pattern, c) and me not in c for c in _processes()):
            return True
        return False
    if keep_awake:
        _keep_awake(True)
    try:
        write(f"=== {datetime.datetime.now():%H:%M} waiting for the conditions")
        while busy():
            time.sleep(poll)
        for j in jobs:
            write(f"=== {datetime.datetime.now():%H:%M} {j}")
            r = subprocess.run(j if os.name == "nt" else shlex.split(j), capture_output=True, text=True, errors="replace", shell=False)
            write((r.stdout + r.stderr).rstrip()); write(f"    exit {r.returncode}")
        write(f"=== {datetime.datetime.now():%H:%M} queue finished")
    finally:
        if keep_awake:
            _keep_awake(False)


def jobs_from_file(path):
    return [l.strip() for l in pathlib.Path(path).read_text(encoding="utf-8").splitlines() if l.strip() and not l.strip().startswith("#")]
