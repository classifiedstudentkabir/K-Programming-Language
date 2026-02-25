# K++ Programming Language

K++ is a natural-English style programming language with a Python-based runtime.
It includes a CLI interpreter, a desktop GUI editor, and a modular runtime in `kpp/`.

## Installation

1. Install Python 3.10+.
2. Clone this repository.
3. (Optional) create and activate a virtual environment.
4. Install dependencies:

```bash
pip install -r requirements.txt
```

## Example Program

```kpp
let name be "Kabir".
print call join with "Hello, ", name.

for i from 1 to 3 then
    print i.
end.
```

## CLI Usage

Run file:

```bash
python kpp/main.py program.kpp
```

Syntax check only:

```bash
python kpp/main.py --check program.kpp
```

Version:

```bash
python kpp/main.py --version
```

Help:

```bash
python kpp/main.py --help
```

## GUI Usage

Start the desktop GUI:

```bash
python gui.py
```

Open a file directly:

```bash
python gui.py programs/for_range_basic.kpp
```

## Screenshot

<img width="1366" height="738" alt="image" src="https://github.com/user-attachments/assets/f8cc1bfd-a3c0-4152-a7d6-816eabc9aabf" />


## Roadmap

- Improve module import diagnostics.
- Expand class/object ergonomics.
- Add automated test suite and CI workflow.
- Publish packaged binary releases for Windows.

## License

© Kabir
