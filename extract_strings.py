import marshal
import sys

pyc_path = '/home/snowaflic/agents/__pycache__/whatsapp_operator.cpython-312.pyc'
out_path = '/home/snowaflic/agents/whatsapp_operator_strings.txt'

try:
    with open(pyc_path, 'rb') as f:
        f.read(16)
        code = marshal.load(f)

    def extract_strings(code_obj, depth=0):
        strings = []
        for const in code_obj.co_consts:
            if isinstance(const, str) and len(const) > 5:
                strings.append(const)
            elif hasattr(const, 'co_consts'):
                strings.extend(extract_strings(const, depth+1))
        return strings

    strings = extract_strings(code)
    with open(out_path, 'w', encoding='utf-8') as f:
        for s in strings:
            f.write(repr(s) + '\n')
    print(f'Extracted {len(strings)} strings to {out_path}')
except Exception as e:
    print(f'Error: {e}')
