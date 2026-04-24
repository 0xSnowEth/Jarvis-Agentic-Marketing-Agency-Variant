#!/usr/bin/env python3
"""Decompile whatsapp_operator.cpython-312.pyc back to source."""
import subprocess, sys

# Try to install decompile3 or uncompyle6
try:
    import decompile3
except ImportError:
    try:
        import uncompyle6
    except ImportError:
        print("Installing pycdc alternative - trying decompyle3...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "decompile3"], 
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Try multiple decompilers
pyc_path = "/home/snowaflic/agents/__pycache__/whatsapp_operator.cpython-312.pyc"
out_path = "/home/snowaflic/agents/whatsapp_operator_recovered.py"

success = False

# Method 1: decompile3
try:
    from decompile3.semantics.pysource import deparse_code_with_map
    import marshal
    with open(pyc_path, "rb") as f:
        f.read(16)  # skip header
        code = marshal.load(f)
    result = deparse_code_with_map(code, out=open(out_path, "w"))
    print(f"Method 1 (decompile3): SUCCESS -> {out_path}")
    success = True
except Exception as e:
    print(f"Method 1 (decompile3): FAILED - {e}")

# Method 2: uncompyle6
if not success:
    try:
        import uncompyle6
        with open(out_path, "w") as f:
            uncompyle6.decompile_file(pyc_path, f)
        print(f"Method 2 (uncompyle6): SUCCESS -> {out_path}")
        success = True
    except Exception as e:
        print(f"Method 2 (uncompyle6): FAILED - {e}")

# Method 3: dis module to at least extract string constants
if not success:
    print("\nDecompilers failed. Extracting string constants from bytecode...")
    import marshal
    with open(pyc_path, "rb") as f:
        f.read(16)
        code = marshal.load(f)
    
    def extract_strings(code_obj, depth=0):
        strings = []
        for const in code_obj.co_consts:
            if isinstance(const, str) and len(const) > 10:
                strings.append(const)
            elif hasattr(const, 'co_consts'):
                strings.extend(extract_strings(const, depth+1))
        return strings
    
    strings = extract_strings(code)
    with open(out_path, "w") as f:
        f.write("# STRING CONSTANTS EXTRACTED FROM BYTECODE\n")
        f.write(f"# Total strings found: {len(strings)}\n\n")
        for i, s in enumerate(strings):
            f.write(f"# --- String {i} ---\n")
            f.write(f"# {repr(s)}\n\n")
    print(f"Extracted {len(strings)} string constants -> {out_path}")

if not success:
    # Method 4: try pycdc via subprocess
    try:
        result = subprocess.run(["pycdc", pyc_path], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            with open(out_path, "w") as f:
                f.write(result.stdout)
            print(f"Method 4 (pycdc): SUCCESS -> {out_path}")
            success = True
    except FileNotFoundError:
        print("pycdc not available")
