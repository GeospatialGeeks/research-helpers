# Job queue (`research_helpers.jobqueue`)

Run long jobs one after another, after something else has finished, with a log (overnight runs).

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

## Functions and classes

**`run_queue(jobs, log, after_pid=None, after_file=None, after_text=None, wait_for_pattern=None, keep_awake=False, poll=60)`**
