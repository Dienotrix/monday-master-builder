# Windows checks

A check run for the plugin's record scripts on a Windows machine. It is development tooling: the `tests/` folder never ships with the plugin.

## What it checks

`run_windows_checks.py` works only in temporary folders it creates and removes again. It never touches the plugin's own home folder, your Claude Code settings or any monday account. It does three things:

1. **System report.** Your Windows and Python details, which file-lock method the scripts use on this Python, the list of installed Pythons (`py -0p`), and whether this Python came from python.org, the Microsoft Store, MSYS2 or Cygwin.
2. **Unit tests.** The full unit test suite, run with the same Python.
3. **Lease and lock checks.** These need a real Windows machine:
   - several processes taking the record lock in turn;
   - eight processes racing to take the build lease;
   - a process holding the lock being force-closed;
   - the lock being freed after an error;
   - files held open by another program while the lease changes;
   - the lock method under each installed Python;
   - the same folder written two ways (upper or lower case drive letter, short 8.3 name).

Four further checks (a OneDrive folder, Ctrl+C, WSL and a network share) need a person at the keyboard. The results file lists short steps for each. They are optional.

The whole run takes a few minutes. It ends normally even when a check finds a problem, because the findings are what the run is for.

## How to run it

1. **Have two Pythons ready: Python 3.9 and the newest Python 3.** Use the installers from python.org (3.9.13 is the last 3.9 release with a Windows installer). If you use uv, `uv python install 3.9` gives you 3.9. To see which Pythons you already have, open PowerShell and run `py -0p`.
2. **Unzip the bundle** to any folder, then open PowerShell in that folder (the one holding `plugins` and `tests`).
3. **Run the checks twice**, once with each Python:

   ```
   py -3.9 tests\windows\run_windows_checks.py
   py tests\windows\run_windows_checks.py
   ```

   You can also ask Claude Code, opened in that folder, to run the same two commands.

If `py -3.9` answers that no such Python is installed (a Python from uv may not be listed), run the same file with that Python's full path instead, for example `C:\path\to\python.exe tests\windows\run_windows_checks.py`.

If you are short of time, add `--quick` to run only the system report and the unit tests.

## What to send back

Each run writes a results file next to the script, named after the Python it ran under, for example:

- `tests\windows\windows-results-3.9.md`
- `tests\windows\windows-results-3.13.md`

Send back both files. If a run stops before it writes its file, send what it printed in the window instead.
