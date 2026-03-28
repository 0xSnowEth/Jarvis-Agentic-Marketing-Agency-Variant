import subprocess
res = subprocess.run(["python", "pipeline.py", "--client", "Burger_grillz", "--topic", "test"], capture_output=True, text=True)
with open("test_out.txt", "w", encoding="utf-8") as f:
    f.write(res.stdout)
    f.write("\n======================\n")
    f.write(res.stderr)
