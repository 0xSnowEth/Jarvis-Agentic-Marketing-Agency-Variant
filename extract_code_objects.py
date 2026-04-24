"""Extract all code objects (functions, methods) from the .pyc file."""
import dis
import marshal
import sys
import types

PYC_PATH = "__pycache__/whatsapp_operator.cpython-312.pyc"

with open(PYC_PATH, "rb") as f:
    f.read(16)  # Skip magic, flags, timestamp, size (Python 3.12 header)
    code = marshal.load(f)

def collect_code_objects(co, prefix=""):
    """Recursively collect all code objects."""
    results = []
    name = f"{prefix}.{co.co_name}" if prefix else co.co_name
    results.append({
        "name": name,
        "qualname": getattr(co, 'co_qualname', co.co_name),
        "argcount": co.co_argcount,
        "varnames": list(co.co_varnames[:co.co_argcount + co.co_kwonlyargcount]),
        "firstlineno": co.co_firstlineno,
        "consts_strings": [c for c in co.co_consts if isinstance(c, str)],
        "consts_count": len(co.co_consts),
        "names": list(co.co_names),  # Global names referenced
        "nlocals": co.co_nlocals,
        "stacksize": co.co_stacksize,
        "flags": co.co_flags,
    })
    for const in co.co_consts:
        if isinstance(const, types.CodeType):
            results.extend(collect_code_objects(const, name))
    return results

all_objects = collect_code_objects(code)

print(f"Total code objects found: {len(all_objects)}")
print(f"Module starts at line: {code.co_firstlineno}")
print()

# Group by top-level functions
top_level = [o for o in all_objects if o["qualname"].count(".") == 0 or o["qualname"].count("<") > 0]
nested = [o for o in all_objects if o["qualname"].count(".") > 0 and o["qualname"].count("<") == 0]

print("=" * 80)
print("TOP-LEVEL FUNCTIONS (sorted by line number)")
print("=" * 80)
for obj in sorted(all_objects, key=lambda x: x["firstlineno"]):
    if obj["name"] == "<module>":
        continue
    indent = "  " if "." in obj["qualname"] and "<" not in obj["qualname"] else ""
    args = ", ".join(obj["varnames"])
    print(f"{indent}L{obj['firstlineno']:>4}  {obj['qualname']}({args})")
    # Show key string constants (UI copy)
    ui_strings = [s for s in obj["consts_strings"] if len(s) > 20 and not s.startswith("_")]
    for s in ui_strings[:3]:
        print(f"{indent}       STR: {s[:100]}")
    # Show global names referenced (function calls etc)
    important_names = [n for n in obj["names"] if not n.startswith("__")]
    if important_names:
        print(f"{indent}       CALLS: {', '.join(important_names[:15])}")
    print()

print("=" * 80)
print("MODULE-LEVEL NAMES (globals referenced in module body)")
print("=" * 80)
print(", ".join(code.co_names[:50]))
