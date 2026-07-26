# KeydMapper

KeydMapper is a visual editor for
[keyd](https://github.com/rvaiya/keyd) configuration files. It provides a
keyboard and mouse layout editor while keeping the generated keyd config
available as a live, editable preview.

## Features

- Visual editing for layers, bindings, macros, overloads, oneshots, and other
  keyd actions
- Live config preview with syntax highlighting and completion
- Round-trip text editing without removing comments or unsupported directives
- Custom physical keyboard and mouse layouts
- Safe Apply, Enable, and Disable operations through a restricted Polkit helper

KeydMapper is intended for Linux systems running keyd. A bad mapping can make
input unusable; keyd's emergency stop sequence is
`Backspace` + `Escape` + `Enter`.

## Installation

### Arch Linux (AUR)

```bash
yay -S keyd-mapper
sudo systemctl enable --now keyd
```

### From source

Install keyd, Python 3.10 or newer, Qt/PySide6, and Polkit first. Then run:

```bash
git clone https://github.com/Martin3225/KeydMapper.git
cd KeydMapper
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
sudo ./scripts/install-system-helper.sh
sudo systemctl enable --now keyd
keyd-mapper
```

The first system change in each KeydMapper session opens a Polkit
authentication dialog. The restricted helper remains available only for that
application session and exits when KeydMapper closes.

## Development

```bash
python -m pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen pytest KeydMapper/tests
```

See [RELEASING.md](RELEASING.md) for the GitHub and AUR release checklist.

## License

[MIT](LICENSE)
