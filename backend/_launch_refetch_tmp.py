"""Detach the outcome-variable fetch so it outlives the shell's 30s limit."""
import subprocess
import sys

args = [sys.executable, "backend/_fetch_ctgov_outcome_variables.py"] + sys.argv[1:]
with open("backend/_refetch.log", "w", encoding="utf-8") as out, open(
    "backend/_refetch.err", "w", encoding="utf-8"
) as err:
    subprocess.Popen(
        args,
        stdout=out,
        stderr=err,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        | subprocess.DETACHED_PROCESS,
    )
print("launched:", " ".join(args[1:]))