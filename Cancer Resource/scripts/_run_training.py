"""Run train_interaction and capture output."""
import subprocess
import sys
import os

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out_path = os.path.join(root, "temp", "train_run.txt")
os.makedirs(os.path.join(root, "temp"), exist_ok=True)

p = subprocess.run(
    [sys.executable, "-m", "src.training.train_interaction", "--mode", "binary"],
    capture_output=True, text=True, cwd=root
)

with open(out_path, "w") as f:
    f.write(f"Return code: {p.returncode}\n")
    f.write("=== STDOUT ===\n")
    f.write(p.stdout)
    f.write("\n=== STDERR ===\n")
    f.write(p.stderr)
    f.write("\n")

print(f"Wrote {out_path}")
print(f"RC={p.returncode}")
print("---STDOUT---")
print(p.stdout[-500:] if len(p.stdout) > 500 else p.stdout)
if p.stderr:
    print("---STDERR---")
    print(p.stderr[-500:] if len(p.stderr) > 500 else p.stderr)