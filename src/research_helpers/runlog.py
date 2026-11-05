"""Compute log: what each run asked, where it ran, what it used, and what it made, kept as one growing record.

Every run appends one JSON line to <log>/runs.jsonl; `report` compiles the lines into runs.md and runs.csv. The aim
is a lasting record of benchmarks, efficiency, energy and secure use that others can learn from, so a run records
facts measured on the machine and marks anything estimated as an estimate.

Python:
    from research_helpers import runlog
    with runlog.run("hem campaign", log="records/compute", question="Does our score rank homes as HEM does?",
                    inputs=["inputs/"], outputs=["results/"]) as r:
        ...                                   # the work
        r.note("swapped wind files")          # comments kept with the run
        r.metric("runs", 2592)                # any figure worth keeping

Command line (wraps any command, on a laptop, a cloud machine or an HPC login node):
    rh runlog --log records/compute --question "..." -- python model.py --area london
    rh runlog-slurm --log records/compute 10547739 10548557      # after jobs end: sacct and seff, saved and summarised
    rh runlog-report records/compute                              # runs.md and runs.csv

What is recorded: start, end and wall time; CPU time of the process and its children; peak memory (psutil when
installed); host, operating system, processor, cores and memory; where it ran (laptop, Slurm job, GitHub Actions,
cloud) from the environment; Python and key package versions; git commit and whether the tree had changes; the
command; inputs and outputs with sizes (and SHA-256 below a limit); remote services named by the caller; notes and
metrics; exit status. Energy is an estimate, core-hours times a stated power per core plus memory power, after the
Green Algorithms method (Lannelongue et al. 2021); the constants are written with each estimate.

What is never recorded: values of environment variables, tokens, keys or passwords. Variable names that look secret
are counted, not listed. Paths of private data are kept, their contents are not.
"""
import contextlib, csv, datetime, hashlib, json, os, platform, re, shutil, socket, subprocess, sys, time
from pathlib import Path

__all__ = ["run", "Run", "slurm", "report", "machine"]

W_PER_CORE = 12.0        # W per core in use; Green Algorithms default for a typical server core, an estimate
W_PER_GB = 0.3725        # W per GB of memory, Green Algorithms default
PUE = 1.67               # data-centre overhead, Green Algorithms default; 1.0 for a laptop
SECRET = re.compile(r"KEY|TOKEN|SECRET|PASS|CRED|AUTH", re.I)
PACKAGES = ("numpy", "pandas", "geopandas", "xarray", "rasterio", "lightgbm", "sklearn", "torch", "zensical")


def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def where():
    """Where this runs, from the environment only."""
    e = os.environ
    if "SLURM_JOB_ID" in e:
        return {"kind": "hpc-slurm", "cluster": e.get("SLURM_CLUSTER_NAME", ""), "job": e.get("SLURM_JOB_ID"),
                "array_task": e.get("SLURM_ARRAY_TASK_ID", ""), "partition": e.get("SLURM_JOB_PARTITION", ""),
                "cpus": e.get("SLURM_CPUS_ON_NODE", ""), "mem_per_cpu_mb": e.get("SLURM_MEM_PER_CPU", ""), "node": e.get("SLURMD_NODENAME", "")}
    if e.get("GITHUB_ACTIONS"):
        return {"kind": "ci-github", "runner": e.get("RUNNER_OS", ""), "workflow": e.get("GITHUB_WORKFLOW", "")}
    for k, name in (("COLAB_RELEASE_TAG", "cloud-colab"), ("AWS_EXECUTION_ENV", "cloud-aws"), ("GOOGLE_CLOUD_PROJECT", "cloud-gcp"),
                    ("AZUREML_RUN_ID", "cloud-azure"), ("JUPYTERHUB_USER", "cloud-jupyterhub")):
        if k in e:
            return {"kind": name}
    return {"kind": "local"}


def machine():
    m = {"host": socket.gethostname(), "os": f"{platform.system()} {platform.release()}", "processor": platform.processor() or platform.machine(),
         "cores_logical": os.cpu_count(), "python": sys.version.split()[0]}
    try:
        import psutil
        m["cores_physical"] = psutil.cpu_count(logical=False)
        m["memory_gb"] = round(psutil.virtual_memory().total / 2**30, 1)
    except ImportError:
        pass
    if shutil.which("nvidia-smi"):
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True, text=True)
        m["gpus"] = [x.strip() for x in r.stdout.splitlines() if x.strip()]
    return m


def _versions():
    out = {}
    for p in PACKAGES:
        mod = sys.modules.get(p)
        if mod is not None:
            out[p] = getattr(mod, "__version__", "")
    return out


def _git(cwd="."):
    try:
        c = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=cwd, capture_output=True, text=True, timeout=10)
        if c.returncode:
            return {}
        d = subprocess.run(["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True, timeout=20)
        return {"commit": c.stdout.strip(), "uncommitted_changes": bool(d.stdout.strip())}
    except (OSError, subprocess.SubprocessError):
        return {}


def _files(paths, hash_limit_mb=50):
    rows = []
    for p in map(Path, paths or []):
        files = [p] if p.is_file() else [x for x in p.rglob("*") if x.is_file()] if p.is_dir() else []
        size = sum(f.stat().st_size for f in files)
        row = {"path": str(p), "files": len(files), "bytes": size}
        if len(files) == 1 and size <= hash_limit_mb * 2**20:
            row["sha256"] = hashlib.sha256(files[0].read_bytes()).hexdigest()
        rows.append(row)
    return rows


def energy(core_hours, mem_gb_hours=0.0, pue=PUE, w_core=W_PER_CORE, w_gb=W_PER_GB):
    kwh = (core_hours * w_core + mem_gb_hours * w_gb) * pue / 1000
    return {"kwh_estimate": round(kwh, 4), "method": "Green Algorithms (Lannelongue et al. 2021)",
            "w_per_core": w_core, "w_per_gb": w_gb, "pue": pue}


class Run:
    def __init__(self, name, log, question="", inputs=(), outputs=(), services=(), project=""):
        self.log = Path(log)
        self.rec = {"name": name, "project": project, "question": question, "start": _now(), "where": where(), "machine": machine(),
                    "command": " ".join(sys.argv), "cwd": os.getcwd(), "git": _git(), "services": list(services),
                    "inputs": _files(inputs), "notes": [], "metrics": {},
                    "secret_like_env_vars_present": sum(1 for k in os.environ if SECRET.search(k))}
        self._outputs, self._t0, self._c0 = list(outputs), time.perf_counter(), os.times()
        self._peak, self._stop, self._kid_cpu = 0, False, {}
        try:
            import psutil, threading
            self._proc = psutil.Process()

            def watch():
                while not self._stop:
                    try:
                        kids = self._proc.children(recursive=True)
                        self._peak = max(self._peak, self._proc.memory_info().rss + sum(c.memory_info().rss for c in kids))
                        for c in kids:          # Windows does not report children's CPU time to os.times; sample it
                            t = c.cpu_times()
                            self._kid_cpu[c.pid] = t.user + t.system
                    except Exception:
                        pass
                    time.sleep(0.5)
            threading.Thread(target=watch, daemon=True).start()
        except ImportError:
            self._proc = None

    def note(self, text):
        self.rec["notes"].append(str(text))

    def metric(self, key, value):
        self.rec["metrics"][key] = value

    def finish(self, status="ok", error=""):
        self._stop = True
        wall = time.perf_counter() - self._t0
        c1 = os.times()
        own = (c1.user - self._c0.user) + (c1.system - self._c0.system)
        kids = (c1.children_user - self._c0.children_user) + (c1.children_system - self._c0.children_system)
        cpu = own + max(kids, sum(self._kid_cpu.values()))      # sampled children can miss the last half second
        cores = self.rec["machine"]["cores_logical"] or 1
        r = self.rec
        r.update({"end": _now(), "status": status, "error": error[-2000:], "wall_s": round(wall, 2), "cpu_s": round(cpu, 2),
                  "cpu_efficiency_of_one_core": round(cpu / wall, 3) if wall else None,
                  "share_of_machine_cores": round(cpu / wall / cores, 4) if wall else None,
                  "peak_memory_gb": round(self._peak / 2**30, 3) if self._peak else None,
                  "outputs": _files(self._outputs), "versions": _versions()})
        pue = 1.0 if r["where"]["kind"] == "local" else PUE
        r["energy"] = energy(cpu / 3600, (self._peak / 2**30) * wall / 3600 if self._peak else 0.0, pue=pue)
        self.log.mkdir(parents=True, exist_ok=True)
        with open(self.log / "runs.jsonl", "a", encoding="utf8") as f:
            f.write(json.dumps(r, default=str) + "\n")
        return r


@contextlib.contextmanager
def run(name, log="records/compute", **kw):
    r = Run(name, log, **kw)
    try:
        yield r
    except BaseException as e:
        r.finish("failed", f"{type(e).__name__}: {e}")
        raise
    else:
        r.finish("ok")


def command(argv, log, name="", question="", project=""):
    """Run a command under the log; returns its exit code."""
    r = Run(name or " ".join(argv)[:80], log, question=question, project=project)
    r.rec["command"] = " ".join(argv)
    code = subprocess.call(argv)
    r.finish("ok" if code == 0 else f"exit {code}")
    return code


SACCT = "JobID,JobName,Partition,State,Submit,Start,End,Elapsed,AllocCPUS,TotalCPU,CPUTimeRAW,ReqMem,MaxRSS,NodeList,ConsumedEnergyRaw"


def _mb(x):
    m = re.match(r"([\d.]+)([KMGT]?)", x or "")
    return float(m[1]) * {"K": 1 / 1024, "M": 1, "G": 1024, "T": 1024**2, "": 1 / 2**20}[m[2]] if m else 0.0


def _sec(t):
    if not t:
        return 0.0
    d, _, t = t.rpartition("-")
    parts = [float(x) for x in t.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return (float(d) if d else 0) * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]


def slurm(jobids, log, name="", question="", project=""):
    """After Slurm jobs end: keep sacct (and seff) output as it came, and append one summary line to runs.jsonl."""
    log = Path(log)
    raw = log / "slurm"
    raw.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = subprocess.run(["sacct", "-P", "-j", ",".join(map(str, jobids)), f"--format={SACCT}"], capture_output=True, text=True).stdout
    (raw / f"sacct_{stamp}.txt").write_text(out, encoding="utf8")
    if shutil.which("seff"):
        (raw / f"seff_{stamp}.txt").write_text("\n".join(subprocess.run(["seff", str(j)], capture_output=True, text=True).stdout for j in jobids), encoding="utf8")
    rows = list(csv.DictReader(out.splitlines(), delimiter="|"))
    steps = [x for x in rows if "." in x["JobID"]]                 # steps hold usage; allocations hold requests
    alloc = [x for x in rows if "." not in x["JobID"]]
    core_s = sum(_sec(x["TotalCPU"]) for x in steps)
    alloc_core_s = sum(float(x["CPUTimeRAW"] or 0) for x in alloc)
    peak = max((_mb(x["MaxRSS"]) for x in steps), default=0)
    req = max((_mb(x["ReqMem"].rstrip("cn")) for x in alloc), default=0)
    starts = [x["Start"] for x in alloc if x["Start"] not in ("", "Unknown", "None")]
    ends = [x["End"] for x in alloc if x["End"] not in ("", "Unknown", "None")]
    rec = {"name": name or f"slurm {jobids[0]}", "project": project, "question": question, "start": min(starts, default=""), "end": max(ends, default=""),
           "where": {"kind": "hpc-slurm", "partitions": sorted({x["Partition"] for x in alloc if x["Partition"]}), "jobs": [str(j) for j in jobids]},
           "status": ",".join(sorted({x["State"].split()[0] for x in alloc if x["State"]})), "tasks": len(alloc),
           "cpu_s": round(core_s, 1), "allocated_core_s": round(alloc_core_s, 1),
           "cpu_efficiency_of_allocation": round(core_s / alloc_core_s, 3) if alloc_core_s else None,
           "peak_memory_gb": round(peak / 1024, 3), "requested_memory_gb": round(req / 1024, 3),
           "memory_efficiency": round(peak / req, 3) if req else None,
           "measured_energy_j": sum(float(x["ConsumedEnergyRaw"] or 0) for x in alloc) or None,
           "energy": energy(alloc_core_s / 3600), "raw": str(raw / f"sacct_{stamp}.txt")}
    with open(log / "runs.jsonl", "a", encoding="utf8") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec, indent=1))
    return rec


def report(log):
    """runs.md and runs.csv from runs.jsonl, with totals."""
    log = Path(log)
    recs = [json.loads(x) for x in (log / "runs.jsonl").read_text(encoding="utf8").splitlines() if x.strip()]
    cols = ["start", "project", "name", "where", "status", "wall_s", "cpu_s", "cpu_eff", "peak_memory_gb", "mem_eff", "kwh_estimate", "question"]
    rows = [{"start": r.get("start", ""), "project": r.get("project", ""), "name": r.get("name", ""), "where": r.get("where", {}).get("kind", ""),
             "status": r.get("status", ""), "wall_s": r.get("wall_s", ""), "cpu_s": r.get("cpu_s", ""),
             "cpu_eff": r.get("cpu_efficiency_of_allocation", r.get("cpu_efficiency_of_one_core", "")), "peak_memory_gb": r.get("peak_memory_gb", ""),
             "mem_eff": r.get("memory_efficiency", ""), "kwh_estimate": r.get("energy", {}).get("kwh_estimate", ""), "question": r.get("question", "")} for r in recs]
    with open(log / "runs.csv", "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(rows)
    num = lambda k: sum(float(x[k]) for x in rows if str(x[k]).replace(".", "", 1).isdigit())
    md = ["# Compute log", "", f"{len(rows)} runs. CPU {num('cpu_s') / 3600:.2f} core-hours. Energy {num('kwh_estimate'):.3f} kWh, estimated "
          f"(Green Algorithms; constants in each record). Built {_now()} from runs.jsonl.", "",
          "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    md += ["| " + " | ".join(str(x[c]).replace("|", "/") for c in cols) + " |" for x in rows]
    (log / "runs.md").write_text("\n".join(md) + "\n", encoding="utf8")
    print(f"{len(rows)} runs -> {log / 'runs.md'}")
    return rows
