#!/usr/bin/env python3
"""Windows check harness for WP2 (development tooling; tests/ never ships).

Run from the repository root on a Windows machine, once under Python 3.9 and once under the newest Python 3:

    py -3.9 tests\\windows\\run_windows_checks.py
    py tests\\windows\\run_windows_checks.py

It reports the system, runs the unit suite with the interpreter it runs under, and runs the automatable items of
the lease review's "What a real Windows run must exercise" list on copies of the unit fixture in temporary folders
it creates (never the real home). Items 6, 7, 8 and 11 are manual: their steps are printed and marked not run.
Everything goes to stdout and to windows-results-<X.Y>.md beside this file. The exit code is 0 whenever the run
completed, whatever it found: the findings are data for the main session.

Flags: --quick runs only the system report and the unit suite; --dry-run does the same and lists the Windows items
as skipped (for a check on macOS); --all-here runs the automatable items on any system (a development aid).
Helpers for the manual items: --copy-fixture DEST, --hold-mutex FOLDER and --try-mutex FOLDER (with --seconds).
Standard library only, Python 3.9 or later; ctypes is used for the Windows calls.
"""
import sys
sys.dont_write_bytecode = True  # nothing cached beside the scripts or the tests (G49)
import argparse, json, os, platform, re, shutil, subprocess, sysconfig, tempfile, threading, time  # noqa: E401,E402
import traceback  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SCRIPTS = REPO / "plugins" / "monday-master-builder" / "scripts"
RECORD_PY = SCRIPTS / "record.py"
FIXTURE_HOME = REPO / "tests" / "unit" / "fixtures" / "home"
CLIENT = "larkmoor-joinery"                       # the fixture's client folder
FIXTURE_EPOCH, FIXTURE_LABEL = 2, "20261105-1405-r2d6"  # the fixture lock: held by strand 001 at epoch 2
ACCOUNT_ID = "10000001"                          # the fixture's bound account id (fictional)
BREAK_YES = "yes, break the lease of 001"
IS_WINDOWS = os.name == "nt"
IGNORE = shutil.ignore_patterns(".gitkeep", ".DS_Store")
TRIM = 3000
UTC = "%Y-%m-%dT%H:%M:%SZ"
SANDBOXES = []
MC = None  # mmb_common, imported on first use

GATE = ("import sys, time, runpy\nsys.dont_write_bytecode = True\n"
        "start, script = float(sys.argv[1]), sys.argv[2]\nsys.path.insert(0, sys.argv[3])\n"
        "time.sleep(max(0.0, start - time.time()))\n"
        "sys.argv = [script] + sys.argv[4:]\nrunpy.run_path(script, run_name='__main__')\n")

COUNTER_WORKER = ("import sys, time; sys.dont_write_bytecode = True; sys.path.insert(0, sys.argv[1]);"
                  " import mmb_common; from pathlib import Path; root = Path(sys.argv[2])\n"
                  "counter = root / 'counter.txt'\n"
                  "for _ in range(20):\n    with mmb_common.record_mutex(root):\n"
                  "        value = int(counter.read_text()); time.sleep(0.004); counter.write_text(str(value + 1))\n")

HOLDER = ("import sys, time; sys.dont_write_bytecode = True; sys.path.insert(0, sys.argv[1]);"
          " import mmb_common; from pathlib import Path\n"
          "hold = mmb_common.record_mutex(Path(sys.argv[2])); hold.__enter__()\n"
          "print('held', flush=True); time.sleep(float(sys.argv[3]))\n")

TAKER = ("import sys, time; sys.dont_write_bytecode = True; sys.path.insert(0, sys.argv[1]);"
         " import mmb_common; from pathlib import Path\n"
         "start = time.monotonic()\n"
         "try:\n    with mmb_common.record_mutex(Path(sys.argv[2]), timeout=float(sys.argv[3])):\n"
         "        print('acquired %.2f' % (time.monotonic() - start))\n"
         "except mmb_common.MMBError as exc:\n    print('refused %.2f %s' % (time.monotonic() - start, exc))\n")


# Small helpers: text, trimming, subprocesses, sandboxes.

def trim(text, limit=TRIM):
    text = (text or "").replace("```", "'''").rstrip()
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + "\n[... %d characters trimmed ...]\n" % (len(text) - limit) + text[-half:]

def decode(data):
    """A child's output as text with LF line endings: Windows children write CRLF, and the results file keeps one."""
    return (data or b"").decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")

def utc(moment=None):
    return (moment or datetime.now(timezone.utc)).strftime(UTC)

def mmb():
    """mmb_common from the repository's scripts folder, imported once."""
    global MC
    if MC is None:
        if str(SCRIPTS) not in sys.path:
            sys.path.insert(0, str(SCRIPTS))
        import mmb_common
        MC = mmb_common
    return MC

def run(cmd, timeout=120, env=None, cwd=None):
    """(exit code or None, stdout, stderr) of an argument list, never through a shell."""
    try:
        done = subprocess.run([str(part) for part in cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout, env=env, cwd=None if cwd is None else str(cwd))
        return done.returncode, decode(done.stdout), decode(done.stderr)
    except subprocess.TimeoutExpired as exc:
        return None, decode(exc.stdout), decode(exc.stderr) + "\n[timed out after %s seconds]" % timeout
    except OSError as exc:
        return None, "", "could not start %s: %s" % (cmd[0], exc)

def as_json(text):
    try:
        return json.loads(text)
    except ValueError:
        return None


class Sandbox:
    """A copy of the unit fixture home in a new temporary folder whose name holds a space, with MMB_HOME pointed
    at it and HOME and USERPROFILE at an empty canary folder, so no child process can reach the real home."""

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mmb win check "))
        SANDBOXES.append(self)
        self.canary = self.tmp / "canary"
        self.canary.mkdir()
        self.home = Path(shutil.copytree(str(FIXTURE_HOME), str(self.tmp / "mmb home"), ignore=IGNORE))
        self.root = self.home / "clients" / CLIENT
        self.env = dict(os.environ, MMB_HOME=str(self.home), HOME=str(self.canary), USERPROFILE=str(self.canary),
                        PYTHONDONTWRITEBYTECODE="1")

    def record(self, *args, timeout=120):
        """record.py --record <root> args: (code, parsed JSON or None, stdout, stderr)."""
        code, out, err = run([sys.executable, RECORD_PY, "--record", self.root] + list(args), timeout, self.env, self.tmp)
        return code, as_json(out), out, err

    def gated(self, arglists, delay=3.0):
        """Start one record.py per argument list, each waiting until the same wall-clock moment, then collect."""
        start = time.time() + delay
        procs = [subprocess.Popen([sys.executable, "-c", GATE, repr(start), str(RECORD_PY), str(SCRIPTS),
                                   "--record", str(self.root)] + [str(a) for a in args], cwd=str(self.tmp),
                                  env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for args in arglists]
        results = []
        for proc in procs:
            try:
                out, err = proc.communicate(timeout=120)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate()
            results.append((proc.returncode, as_json(decode(out)), decode(out), decode(err)))
        return results

    def lock(self):
        return json.loads((self.root / ".work" / "lock.json").read_text(encoding="utf-8"))

    def set_lock(self, **changes):
        lock = self.lock()
        lock.update(changes)
        (self.root / ".work" / "lock.json").write_bytes((json.dumps(lock, indent=2, ensure_ascii=False) + "\n")
                                                        .encode("utf-8"))

    def released(self):
        """The fixture's lease released (state released, epoch 2), as the start of a take."""
        code, data, out, err = self.record("lease", "release", "--epoch", FIXTURE_EPOCH, "--label", FIXTURE_LABEL)
        if code != 0:
            raise RuntimeError("setup: releasing the fixture lease exited %s: %s %s" % (code, trim(out, 800),
                                                                                         trim(err, 800)))

    def taken(self):
        """Released, then taken by strand 001: returns (epoch, label)."""
        self.released()
        code, data, out, err = self.record("lease", "take", "--strand", "001")
        if code != 0 or not data:
            raise RuntimeError("setup: lease take exited %s: %s %s" % (code, trim(out, 800), trim(err, 800)))
        return data["epoch"], data["session_label"]

    def stale(self):
        """A held lease whose heartbeat is two hours old by this machine's clock."""
        self.set_lock(heartbeat_at=utc(datetime.now(timezone.utc) - timedelta(hours=2)))

    def lock_state(self):
        """The lock's state, epoch and label alone (lock.json is never the held file in item 5)."""
        try:
            lock = self.lock()
            return {"state": lock.get("state"), "epoch": lock.get("epoch"), "label": lock.get("session_label")}
        except Exception as exc:
            return {"error": "%s: %s" % (type(exc).__name__, exc)}

    def mirrors(self):
        """The lock's state, epoch and label, and whether CLIENT.md and account.json mirror it."""
        try:
            mc, lock = mmb(), self.lock()
            held = lock.get("state") == "held"
            line = "%s %s (%s)" % (lock["strand"], lock["version"], lock["session_label"]) if held else "none"
            client = mc.front_matter(mc.read_text(self.root / "CLIENT.md")).get("lease")
            account = json.loads((self.root / "account.json").read_text(encoding="utf-8"))["guard_index"]["lease"]
            want = {key: lock.get(key) for key in ("strand", "epoch", "session_label", "heartbeat_at")}
            return {"state": lock.get("state"), "epoch": lock.get("epoch"), "label": lock.get("session_label"),
                    "mirrors_agree": client == line and account == want}
        except Exception as exc:  # a held file or a torn lock is data here
            return {"error": "%s: %s" % (type(exc).__name__, exc)}

    def cleanup(self):
        notes = []
        try:
            if self.canary.exists() and any(self.canary.iterdir()):
                notes.append("something wrote into the stand-in home: %s" % sorted(
                    p.name for p in self.canary.iterdir()))
        except OSError:
            pass
        shutil.rmtree(str(self.tmp), ignore_errors=True)
        if self.tmp.exists():
            notes.append("temporary folder not fully removed (a handle may still be open): %s" % self.tmp)
        return notes


class Item:
    def __init__(self, key, title):
        self.key, self.title = key, title
        self.status, self.outcome, self.summary, self.details, self.output = "not run", None, "", [], ""

    def note(self, text):
        self.details.append(text)


def guarded(item, body, *args):
    """Run one item; any exception becomes an `error` outcome with its traceback, never a crash."""
    item.status = "ran"
    started = time.monotonic()
    try:
        body(item, *args)
    except Exception:
        item.outcome, item.summary = "error", item.summary or "the check itself raised"
        item.output = trim((item.output + "\n" if item.output else "") + traceback.format_exc(), 4000)
    item.note("took %.1f s" % (time.monotonic() - started))
    return item


# Step 1: the system report.

def flavour():
    """Where this Python came from, as far as it can be told."""
    exe = sys.executable or ""
    base = getattr(sys, "base_prefix", sys.prefix)
    joined = " ".join((exe, base, sys.prefix)).replace("/", "\\").lower()
    plat = sysconfig.get_platform()
    if sys.platform == "cygwin":
        return "Cygwin (POSIX emulation: reports posix, emulated flock)"
    if sys.platform == "msys":
        return "MSYS2 msys runtime (POSIX emulation: reports posix, emulated flock)"
    if os.name == "nt" and plat.startswith("mingw"):
        return "MSYS2 MinGW build (native Windows, msvcrt branch)"
    if os.name != "nt":
        return "not Windows (%s)" % sys.platform
    if "windowsapps" in joined or "pythonsoftwarefoundation.python" in joined:
        return "Microsoft Store"
    if "conda" in sys.version.lower() or (Path(sys.prefix) / "conda-meta").exists():
        return "conda"
    if "\\uv\\python\\" in joined or "cpython-3" in joined:
        return "uv-managed (python-build-standalone, an MSVC build like python.org's)"
    if "MSC" in sys.version:
        return "python.org-style MSVC build (most likely the python.org installer)"
    return "unknown"

def mutex_branch():
    branch = "msvcrt" if os.name == "nt" else "fcntl"
    try:
        __import__(branch)
        return branch + " (imports)"
    except ImportError as exc:
        return branch + " (does NOT import: %s)" % exc

def mutex_probe():
    """Take and release the record mutex once on a temporary folder."""
    folder = Path(tempfile.mkdtemp(prefix="mmb mutex probe "))
    try:
        mc = mmb()
        with mc.record_mutex(folder, timeout=5):
            with mc.record_mutex(folder, timeout=5):
                pass
        return "ok (taken, re-entered, released)"
    except Exception as exc:
        return "failed: %s: %s" % (type(exc).__name__, exc)
    finally:
        shutil.rmtree(str(folder), ignore_errors=True)

def system_report(with_launcher=True):
    report = {"os.name": os.name, "sys.platform": sys.platform, "sys.version": sys.version.replace("\n", " "),
              "sys.executable": sys.executable, "sys.prefix": sys.prefix,
              "sys.base_prefix": getattr(sys, "base_prefix", sys.prefix),
              "virtual environment": getattr(sys, "base_prefix", sys.prefix) != sys.prefix,
              "platform": platform.platform(), "machine": platform.machine(),
              "sysconfig platform": sysconfig.get_platform(), "python source": flavour(),
              "mmb_common mutex branch": mutex_branch(), "mutex probe": mutex_probe(),
              "temp folder": tempfile.gettempdir(), "filesystem encoding": sys.getfilesystemencoding(),
              "stdout encoding": getattr(sys.stdout, "encoding", None)}
    if with_launcher:
        launcher = shutil.which("py")
        if launcher:
            code, out, err = run([launcher, "-0p"], timeout=30)
            report["py -0p"] = (out + err).strip() or "(no output, exit %s)" % code
        else:
            report["py -0p"] = "no py launcher on PATH"
    return report

def interpreters_from_launcher(text):
    """The interpreter paths listed by `py -0p`, in order, without repeats."""
    found = []
    for line in (text or "").splitlines():
        match = re.search(r"([A-Za-z]:\\.*?\.exe)\s*$", line.strip())
        if match and match.group(1) not in found:
            found.append(match.group(1))
    return found

def other_pythons():
    """MSYS2 and Cygwin Pythons in their usual places, when present."""
    found = []
    for pattern in (r"C:\msys64\usr\bin\python3.exe", r"C:\msys64\mingw64\bin\python3.exe",
                    r"C:\msys64\ucrt64\bin\python3.exe", r"C:\msys64\clang64\bin\python3.exe",
                    r"C:\cygwin64\bin\python3.exe", r"C:\cygwin\bin\python3.exe"):
        if IS_WINDOWS and Path(pattern).is_file():
            found.append(pattern)
    return found


# Step 2: the unit suite.

def unit_suite(item):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    code, out, err = run([sys.executable, "-m", "unittest", "discover", "-s", "tests/unit"], 1800, env, REPO)
    text = out + err
    ran = re.findall(r"^Ran (\d+) tests? in ([\d.]+)s", text, re.M)
    last = [line for line in text.strip().splitlines() if line.startswith(("OK", "FAILED"))]
    failed = re.findall(r"^(FAIL|ERROR): (.+)$", text, re.M)
    item.outcome = "pass" if code == 0 and last and last[-1].startswith("OK") else "fail"
    item.summary = "%s; %s" % ("ran %s tests in %s s" % ran[-1] if ran else "no 'Ran' line (exit %s)" % code,
                               last[-1] if last else "no result line")
    for kind, name in failed:
        item.note("%s: %s" % (kind, name))
    blocks = text.split("=" * 70)
    item.output = trim("\n".join(("=" * 70) + block for block in blocks[1:]) if failed else text[-TRIM:], 20000)


# Step 3: the review's Windows items.

def item1_mutex(item):
    mc, sb = mmb(), Sandbox()
    item.note("branch taken: %s" % mutex_branch())
    (sb.root / "counter.txt").write_text("0", encoding="utf-8")
    started = time.monotonic()
    procs = [subprocess.Popen([sys.executable, "-c", COUNTER_WORKER, str(SCRIPTS), str(sb.root)], env=sb.env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(4)]
    codes, errors = [], []
    for proc in procs:
        try:
            _, err = proc.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            proc.kill()
            _, err = proc.communicate()
        codes.append(proc.returncode)
        if err:
            errors.append(decode(err))
    counter = (sb.root / "counter.txt").read_text(encoding="utf-8")
    size = (sb.root / ".work" / "record.mutex").stat().st_size
    serialised = codes == [0] * 4 and counter == "80" and size == 0
    item.note("4 processes x 20 locked read-sleep-write cycles: exits %s, counter %s (want 80), mutex file %d bytes "
              "(want 0), %.1f s" % (codes, counter, size, time.monotonic() - started))
    with mc.record_mutex(sb.root):
        with mc.record_mutex(sb.root):
            reentrant = True
    item.note("re-entrance in one thread: %s" % ("ok" if reentrant else "failed"))
    held, done, outcome = threading.Event(), threading.Event(), {}

    def holder():
        with mc.record_mutex(sb.root):
            held.set()
            done.wait(20)
    thread = threading.Thread(target=holder)
    thread.start()
    held.wait(20)
    started = time.monotonic()
    try:
        with mc.record_mutex(sb.root, timeout=0.5):
            outcome["second"] = "ENTERED (a second handle in this process was not refused)"
    except mc.MMBError as exc:
        outcome["second"] = "refused after %.2f s, exit code %s, field %s" % (
            time.monotonic() - started, exc.code, exc.findings[0]["field"])
    finally:
        done.set()
        thread.join()
    refused = outcome["second"].startswith("refused") and "field record.mutex" in outcome["second"]
    item.note("second handle in this process (another thread), timeout 0.5 s: %s" % outcome["second"])
    item.outcome = "pass" if serialised and reentrant and refused else "fail"
    item.summary = "serialised: %s; re-entrant: %s; second handle refused with the timeout: %s" % (
        serialised, reentrant, refused)
    item.output = trim("\n".join(errors))

def item2_races(item):
    sb = Sandbox()
    sb.released()
    results = sb.gated([["lease", "take", "--strand", "001"]] * 8)
    winners = [data for code, data, _, _ in results if code == 0 and data]
    codes = [code for code, _, _, _ in results]
    state = sb.mirrors()
    take_ok = (len(winners) == 1 and codes.count(1) == 7 and state.get("state") == "held" and state.get("epoch") == 3
               and state.get("label") == winners[0].get("session_label") and state.get("mirrors_agree"))
    item.note("take race, 8 processes: exits %s; lock after %s; winner's label %s" % (
        codes, state, winners[0].get("session_label") if winners else None))
    output = [err for _, _, _, err in results if err.strip()]
    rounds = []
    for number in range(3):
        sb = Sandbox()
        epoch, label = sb.taken()
        sb.stale()
        brk = ["lease", "break", "--epoch", epoch, "--label", label, "--for-strand", "001", "--user-yes", BREAK_YES,
               "--account-id", ACCOUNT_ID, "--choice", "resume"]
        ref = ["lease", "refresh", "--epoch", epoch, "--label", label]
        results = sb.gated([brk, ref, brk, ref, brk, ref])
        breaks = [code for code, _, _, _ in results[0::2]]
        refreshes = [code for code, _, _, _ in results[1::2]]
        state = sb.mirrors()
        good = state.get("mirrors_agree") and (
            (state.get("state") == "broken" and breaks.count(0) == 1 and refreshes.count(0) == 0)
            or (state.get("state") == "held" and breaks.count(0) == 0 and refreshes.count(0) >= 1))
        rounds.append(good)
        item.note("refresh against break, round %d (3 breaks, 3 refreshes on a stale lease): break exits %s, refresh "
                  "exits %s; lock after %s; consistent: %s" % (number + 1, breaks, refreshes, state, bool(good)))
        output += [err for _, _, _, err in results if err.strip()]
    item.outcome = "pass" if take_ok and all(rounds) else "fail"
    item.summary = "take race: one winner, epoch 3, mirrors agree: %s; refresh against break consistent in %d of 3 " \
                   "rounds" % (bool(take_ok), sum(1 for good in rounds if good))
    item.output = trim("\n".join(output))

def read_line(proc, seconds):
    """The first stdout line of a child, or None after `seconds`."""
    box = []
    reader = threading.Thread(target=lambda: box.append(proc.stdout.readline()), daemon=True)
    reader.start()
    reader.join(seconds)
    return decode(box[0]).strip() if box else None

def item3_killed(item):
    mc, sb = mmb(), Sandbox()
    proc = subprocess.Popen([sys.executable, "-c", HOLDER, str(SCRIPTS), str(sb.root), "120"], env=sb.env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    line = read_line(proc, 30)
    if line != "held":
        proc.kill()
        _, err = proc.communicate()
        item.outcome, item.summary = "error", "the holding child never reported the mutex held (%r)" % line
        item.output = trim(decode(err))
        return
    started = time.monotonic()
    proc.kill()  # TerminateProcess on Windows, as taskkill /F
    try:
        with mc.record_mutex(sb.root, timeout=60):
            waited = time.monotonic() - started
    except mc.MMBError:
        waited = None
    proc.wait(30)
    exited = time.monotonic() - started
    item.note("child exit code after kill: %s; it had exited %.2f s after the kill" % (proc.returncode, exited))
    if waited is None:
        item.outcome, item.summary = "fail", "the mutex was still held 60 s after the holder was killed"
    else:
        item.outcome = "pass" if waited < mc.MUTEX_TIMEOUT else "fail"
        item.summary = "another process acquired the mutex %.2f s after Popen.kill() (pass under the %d s mutex " \
                       "timeout)" % (waited, mc.MUTEX_TIMEOUT)
    code, out, err = run([sys.executable, "-c", TAKER, SCRIPTS, sb.root, "5"], 30, sb.env)
    item.note("a fresh process afterwards: %s" % (out.strip() or err.strip()))

def item4_unlock_after_raise(item):
    mc, sb = mmb(), Sandbox()
    try:
        with mc.record_mutex(sb.root):
            raise ValueError("probe raised inside the hold")
    except ValueError as exc:
        seen = "ValueError reached the caller unmasked (%s)" % exc
        masked = False
    except Exception as exc:
        seen, masked = "MASKED: %s: %s reached the caller instead of ValueError" % (type(exc).__name__, exc), True
    item.note(seen)
    try:
        with mc.record_mutex(sb.root, timeout=1):
            again = "ok"
    except mc.MMBError as exc:
        again = "refused: %s" % exc
    item.note("retaken in this process at once: %s" % again)
    code, out, err = run([sys.executable, "-c", TAKER, SCRIPTS, sb.root, "5"], 30, sb.env)
    other = out.strip() or err.strip()
    item.note("taken by another process: %s" % other)
    path = sb.root / ".work" / "record.mutex"
    with open(str(path), "a+b") as handle:
        mc._os_lock(handle, True)
        handle.seek(0, 2)
        try:
            mc._os_lock(handle, False)
            direct = "ok (unlock after the position moved does not raise)"
        except Exception as exc:
            direct = "RAISED %s: %s" % (type(exc).__name__, exc)
    item.note("_os_lock unlock with the file position moved: %s" % direct)
    good = not masked and again == "ok" and other.startswith("acquired") and direct.startswith("ok")
    item.outcome = "pass" if good else "fail"
    item.summary = "error kept, mutex free afterwards in and out of process, direct unlock clean: %s" % good


# Item 5: sharing violations through CreateFileW.

GENERIC_READ, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, FILE_SHARE_READ = 0x80000000, 3, 0x80, 0x1

def kernel32():
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                wintypes.DWORD, wintypes.HANDLE]
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.CloseHandle.restype = wintypes.BOOL
    k32.GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    k32.GetShortPathNameW.restype = wintypes.DWORD
    k32.GetLongPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    k32.GetLongPathNameW.restype = wintypes.DWORD
    return ctypes, k32

def hold_file(path, share):
    """Open `path` for reading with the given share mode; returns a handle to close."""
    ctypes, k32 = kernel32()
    handle = k32.CreateFileW(str(path), GENERIC_READ, share, None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
    if handle is None or handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), "CreateFileW failed on %s" % path)
    return handle

def close_file(handle):
    kernel32()[1].CloseHandle(handle)

def first_problem(data, root):
    """The first finding of a record.py answer, the record folder shortened, fit for a table cell."""
    if not isinstance(data, dict):
        return "no JSON object"
    found = data.get("error") or (data.get("refusals") or [{}])[0]
    text = "%s / %s: %s" % (found.get("file"), found.get("field"), trim(str(found.get("problem")), 300))
    return text.replace(str(root), "<record>").replace("|", "/").replace("\n", " ")

def item5_sharing(item):
    if not IS_WINDOWS:
        item.status, item.outcome, item.summary = "skipped: not Windows", None, "needs CreateFileW share modes"
        return
    rows, good_all = [], True
    for share, share_name in ((0, "share mode 0"), (FILE_SHARE_READ, "read sharing only (writes denied)")):
        for held in ("account.json", "CLIENT.md", "log.md"):
            for command in ("take", "release", "break"):
                sb = Sandbox()
                if command == "take":
                    sb.released()
                    args = ["lease", "take", "--strand", "001"]
                else:
                    epoch, label = sb.taken()
                    if command == "release":
                        args = ["lease", "release", "--epoch", epoch, "--label", label]
                    else:
                        sb.stale()
                        args = ["lease", "break", "--epoch", epoch, "--label", label, "--for-strand", "001",
                                "--user-yes", BREAK_YES, "--account-id", ACCOUNT_ID, "--choice", "resume"]
                before = sb.lock_state()
                handle = hold_file(sb.root / held, share)
                try:
                    try:
                        with open(str(sb.root / held), "r+b"):
                            verified = "NOT effective (a write open succeeded)"
                    except OSError as exc:
                        verified = "effective (%s)" % type(exc).__name__
                    code, data, out, err = sb.record(*args)
                    during = sb.lock_state()
                finally:
                    close_file(handle)
                retry = sb.record(*args)
                sync = sb.record("lease", "sync")
                after = sb.mirrors()
                one_json = isinstance(data, dict) and "Traceback" not in err
                unchanged = "error" not in during and during == before
                committed = isinstance(data, dict) and "committed" in data
                good = one_json and (code == 0 or unchanged or committed)
                good_all = good_all and good
                rows.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                    share_name, held, command, verified, code, first_problem(data, sb.root) if code else "ok",
                    "lock unchanged" if unchanged else "lock changed to %s/%s" % (during.get("state"),
                                                                               during.get("epoch")),
                    "yes" if committed else "no", "exit %s" % retry[0], "exit %s; mirrors agree after: %s" % (
                        sync[0], after.get("mirrors_agree"))))
                if not one_json:
                    item.output += "\n[%s, %s, %s] stdout: %s\nstderr: %s" % (share_name, held, command,
                                                                               trim(out, 600), trim(err, 600))
    item.details += ["| hold | file | command | hold check | exit | first finding | lock | committed | retry after "
                     "close | lease sync |", "|---|---|---|---|---|---|---|---|---|---|"] + rows
    item.outcome = "pass" if good_all else "fail"
    item.summary = "every command answered with one JSON object and either left the lease unchanged or reported " \
                   "what it committed: %s (see the table; the retry column is data)" % good_all
    item.output = trim(item.output, 6000)

def item9_interpreters(item):
    report = system_report()
    paths = interpreters_from_launcher(report.get("py -0p"))
    extra = [p for p in other_pythons() if p not in paths]
    if not paths and not extra:
        paths = [sys.executable]
        item.note("no other interpreter found (%s); this one only" % report.get("py -0p"))
    rows = ["| interpreter | os.name | sys.platform | version | source | branch | mutex probe |",
            "|---|---|---|---|---|---|---|"]
    failures = []
    for path in paths + extra:
        code, out, err = run([path, Path(__file__).resolve(), "--report-json"], 90,
                             dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), REPO)
        lines = [line for line in out.strip().splitlines() if line.startswith("{")]
        data = as_json(lines[-1]) if lines else None
        if not data:
            failures.append("%s: exit %s\n%s" % (path, code, trim(out + err, 800)))
            rows.append("| %s | could not run the report (exit %s) | | | | | |" % (path, code))
            continue
        rows.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            path, data.get("os.name"), data.get("sys.platform"), data.get("sys.version", "").split(" ")[0],
            data.get("python source"), data.get("mmb_common mutex branch"), data.get("mutex probe")))
    item.details += rows
    item.outcome = "observed"
    item.summary = "%d interpreter(s) reported" % (len(paths) + len(extra))
    item.output = trim("\n\n".join(failures))

def spellings(root):
    """Other spellings of the same folder: drive-letter case, 8.3 short and long forms, a symlinked form."""
    text, found = str(root.absolute()), []
    if re.match(r"^[A-Za-z]:", text):
        found.append(("drive letter in the other case", text[0].swapcase() + text[1:]))
    if IS_WINDOWS:
        ctypes, k32 = kernel32()
        for name, call in (("8.3 short path", k32.GetShortPathNameW), ("long path", k32.GetLongPathNameW)):
            buffer = ctypes.create_unicode_buffer(32768)
            length = call(text, buffer, 32768)
            if length and buffer.value and buffer.value != text:
                found.append((name, buffer.value))
            elif not length:
                found.append((name + " (unavailable, error %s)" % ctypes.get_last_error(), None))
            else:
                found.append((name + " (same as given: 8.3 names may be off on this volume)", None))
    else:
        resolved = str(root.resolve())
        if resolved != text:
            found.append(("resolved (symlinked) spelling", resolved))
    return text, found

def item10_spellings(item):
    mc, sb = mmb(), Sandbox()
    given, others = spellings(sb.root)
    item.note("given: %s" % given)
    waits = []
    for name, other in others:
        if other is None:
            item.note("%s: not tested" % name)
            continue
        same = os.path.samefile(given, other)
        resolve_equal = Path(given).resolve() == Path(other).resolve()
        normcase_equal = os.path.normcase(os.path.abspath(given)) == os.path.normcase(os.path.abspath(other))
        started = time.monotonic()
        with mc.record_mutex(Path(given)):
            try:
                with mc.record_mutex(Path(other), timeout=2):
                    result = "entered at once (no self-wait)"
            except mc.MMBError:
                result = "WAITS ON ITSELF (refused after %.1f s)" % (time.monotonic() - started)
                waits.append(name)
        item.note("%s: %s | same file: %s | Path.resolve() equal: %s | normcase(abspath) equal: %s | mutex: %s" % (
            name, other, same, resolve_equal, normcase_equal, result))
    tested = [name for name, other in others if other is not None]
    if not tested:
        item.outcome, item.summary = "skipped", "no second spelling of the folder could be made here"
    else:
        item.outcome = "fail" if waits else "pass"
        item.summary = "the mutex waits on itself for: %s" % ", ".join(waits) if waits else \
            "no self-wait for: %s" % ", ".join(tested)


MANUAL = {
    "6": ("A record home inside a OneDrive-synced folder: take and refresh during an upload", [
        'py tests\\windows\\run_windows_checks.py --copy-fixture "%OneDrive%\\mmb-check" (PowerShell: '
        '"$env:OneDrive\\mmb-check"); it prints the record folder, called RECORD below.',
        'py plugins\\monday-master-builder\\scripts\\record.py --record "RECORD" lease release --epoch 2 --label '
        '20261105-1405-r2d6, then the same with: lease take --strand 001 (note the epoch and label it prints).',
        'While OneDrive shows the folder syncing, run lease refresh --epoch EPOCH --label LABEL a few times, then '
        'lease status. Send the outputs.']),
    "7": ("Ctrl+C in a Windows console during lease take: the state of lock.json afterwards", [
        'py tests\\windows\\run_windows_checks.py --copy-fixture "%TEMP%\\mmb-ctrlc"; release as in item 6.',
        'Run record.py --record "RECORD" lease take --strand 001 and press Ctrl+C straight away; repeat (release '
        'with the printed epoch and label between tries) until one try is cut short.',
        'Run lease status and send its output, and say whether .work\\lock.json still opens as JSON.']),
    "8": ("A WSL session and a native session on one record under C:\\, and the WSL clock after sleep", [
        'py tests\\windows\\run_windows_checks.py --copy-fixture C:\\mmb-check; then in Windows: '
        'py tests\\windows\\run_windows_checks.py --hold-mutex "RECORD" --seconds 60',
        'Within that minute, in WSL from the same folder (under /mnt/c/...): python3 '
        'tests/windows/run_windows_checks.py --try-mutex "/mnt/c/mmb-check/.../larkmoor-joinery" --seconds 5. '
        '"acquired" means the two do not exclude each other.',
        'After the machine has slept and woken: at the same moment run date -u +%FT%TZ in WSL and '
        '(Get-Date).ToUniversalTime().ToString("s") in PowerShell, and send both.']),
    "11": ("msvcrt.locking on an SMB share, if a record is ever kept on one", [
        'py tests\\windows\\run_windows_checks.py --copy-fixture "\\\\server\\share\\mmb-check"',
        'In one window: --hold-mutex "RECORD" --seconds 60; in a second window within the minute: --try-mutex '
        '"RECORD" --seconds 5 ("refused" is right). If a second machine can reach the share, repeat the try there.',
        'Send both outputs.']),
}

AUTOMATED = [("1", "Mutex: processes serialised, re-entrance, timeout (msvcrt branch)", item1_mutex),
             ("2", "Take race with eight processes; refresh against break", item2_races),
             ("3", "Holder killed with Popen.kill() (TerminateProcess, as taskkill /F): time to reacquire",
              item3_killed),
             ("4", "Unlock after the body raised", item4_unlock_after_raise),
             ("5", "Sharing violations on account.json, CLIENT.md and log.md during take, release and break",
              item5_sharing),
             ("9", "Lock branch per interpreter (py -0p and MSYS2 or Cygwin if present)", item9_interpreters),
             ("10", "Drive-letter case and 8.3 short path: does the mutex wait on itself", item10_spellings)]


# Output.

def render(args, report, suite, items, notes, started):
    out = ["# WP2 Windows check results", "",
           "- Run at: %s (UTC), %.0f s" % (utc(), time.monotonic() - started),
           "- Interpreter: %s (%s)" % (sys.executable, sys.version.split(" ")[0]),
           "- Mode: %s" % ("quick" if args.quick else "dry run" if args.dry_run else "all here" if args.all_here
                           else "full"), "", "## 1. System", ""]
    for key, value in report.items():
        if key == "py -0p":
            continue
        out.append("- %s: %s" % (key, value))
    out += ["", "py -0p:", "", "```", trim(str(report.get("py -0p"))), "```", "", "## 2. Unit suite", ""]
    out += render_item(suite, heading=False)
    out += ["## 3. Lease review items", ""]
    for item in items:
        out += ["### Item %s: %s" % (item.key, item.title), ""] + render_item(item, heading=False)
    if notes:
        out += ["## Notes", ""] + ["- %s" % note for note in notes] + [""]
    return "\n".join(out) + "\n"

def render_item(item, heading=True):
    lines = ["- Status: %s" % item.status, "- Result: %s" % (item.outcome or "-")]
    if item.summary:
        lines.append("- Summary: %s" % item.summary)
    table = [d for d in item.details if d.startswith("|")]
    lines += ["- %s" % d for d in item.details if not d.startswith("|")]
    if table:
        lines += [""] + table
    if item.output.strip():
        lines += ["", "```", item.output.strip(), "```"]
    return lines + [""]

def safe_print(text):
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        sys.stdout.write(text.encode(encoding, "replace").decode(encoding, "replace"))
    sys.stdout.flush()


# Manual helpers.

def copy_fixture(dest):
    target = Path(dest) / "mmb check home"
    if target.exists():
        print("refused: %s exists already; give a new folder" % target)
        return 1
    shutil.copytree(str(FIXTURE_HOME), str(target), ignore=IGNORE)
    print("record folder (RECORD in the steps): %s" % (target / "clients" / CLIENT))
    return 0

def hold_mutex(folder, seconds):
    mc = mmb()
    with mc.record_mutex(Path(folder), timeout=10):
        print("held the record mutex of %s for %s seconds (%s branch)" % (folder, seconds, mutex_branch()), flush=True)
        time.sleep(seconds)
    print("released")
    return 0

def try_mutex(folder, seconds):
    mc, started = mmb(), time.monotonic()
    try:
        with mc.record_mutex(Path(folder), timeout=seconds):
            print("acquired after %.2f s (%s branch)" % (time.monotonic() - started, mutex_branch()))
    except mc.MMBError as exc:
        print("refused after %.2f s: %s" % (time.monotonic() - started, exc))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="WP2 Windows checks (development tooling).")
    parser.add_argument("--quick", action="store_true", help="only the system report and the unit suite")
    parser.add_argument("--dry-run", action="store_true", help="as --quick, listing the Windows items as skipped")
    parser.add_argument("--all-here", action="store_true", help="run the automatable items on any system")
    parser.add_argument("--report-json", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--copy-fixture", metavar="DEST", help="manual items: copy the fixture home into DEST")
    parser.add_argument("--hold-mutex", metavar="FOLDER", help="manual items: hold a record's mutex")
    parser.add_argument("--try-mutex", metavar="FOLDER", help="manual items: try to take a record's mutex")
    parser.add_argument("--seconds", type=float, default=60.0)
    args = parser.parse_args(argv)
    if args.report_json:
        print(json.dumps(system_report(with_launcher=False)))
        return 0
    if args.copy_fixture:
        return copy_fixture(args.copy_fixture)
    if args.hold_mutex:
        return hold_mutex(args.hold_mutex, args.seconds)
    if args.try_mutex:
        return try_mutex(args.try_mutex, args.seconds)

    started, notes = time.monotonic(), []
    if sys.version_info < (3, 9):
        notes.append("this Python is %d.%d; the plugin needs 3.9 or later" % sys.version_info[:2])
    if not RECORD_PY.is_file() or not FIXTURE_HOME.is_dir():
        notes.append("the scripts or the unit fixture were not found under %s: run this file from the unzipped "
                     "repository" % REPO)
    safe_print("WP2 Windows checks, %s, Python %s\n\n" % (utc(), sys.version.split(" ")[0]))
    try:
        report = system_report()
    except Exception:
        report = {"error": trim(traceback.format_exc())}
    safe_print("".join("%s: %s\n" % item for item in report.items()) + "\n")

    suite = guarded(Item("unit", "Unit suite"), unit_suite)
    safe_print("Unit suite: %s, %s\n\n" % (suite.outcome, suite.summary))

    items = []
    for key, title, body in AUTOMATED:
        item = Item(key, title)
        if args.quick or args.dry_run:
            item.status = "skipped: not Windows" if args.dry_run and not IS_WINDOWS else \
                "skipped: %s" % ("dry run" if args.dry_run else "--quick")
        elif not IS_WINDOWS and not args.all_here:
            item.status = "skipped: not Windows"
        else:
            safe_print("Item %s: %s ...\n" % (key, title))
            guarded(item, body)
            safe_print("  %s: %s\n" % (item.outcome, item.summary))
        items.append(item)
    for key, (title, steps) in MANUAL.items():
        item = Item(key, title)
        item.status = "not run (manual; optional)"
        item.details = ["step %d: %s" % (number + 1, step) for number, step in enumerate(steps)]
        items.append(item)
    items.sort(key=lambda item: int(item.key))
    for sandbox in SANDBOXES:
        notes += sandbox.cleanup()

    text = render(args, report, suite, items, notes, started)
    target = HERE / ("windows-results-%d.%d.md" % sys.version_info[:2])
    try:
        target.write_bytes(text.encode("utf-8"))
        written = "Results written to %s\n" % target
    except OSError as exc:
        written = "Could not write %s: %s (the results are above)\n" % (target, exc)
    safe_print("\n" + text + "\n" + written)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        for box in SANDBOXES:
            box.cleanup()
        print("\ninterrupted: no results file written")
        sys.exit(1)
