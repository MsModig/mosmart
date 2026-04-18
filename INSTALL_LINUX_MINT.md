# MoSMART Installation Guide for Linux Mint

This guide is tailored for Linux Mint (including Xfce editions).

## Why this guide exists

Linux Mint uses the same Python packaging policy as newer Debian/Ubuntu releases.
If you run `pip install mosmart` directly in system Python, you may get
`externally-managed-environment` (PEP 668).

This is expected and safe behavior.

## Recommended method: pipx

1. Install required system packages:

```bash
sudo apt update
sudo apt install -y smartmontools python3-full pipx
```

2. Ensure pipx binaries are on your PATH:

```bash
pipx ensurepath
```

3. Open a new terminal, then install MoSMART:

```bash
pipx install mosmart
```

4. Start MoSMART web dashboard:

```bash
sudo env "PATH=$PATH" mosmart-web
```

5. Open your browser:

http://localhost:5000

## Alternative method: virtual environment (venv)

Use this if you prefer running from source.

1. Install prerequisites:

```bash
sudo apt update
sudo apt install -y git smartmontools python3-full python3-venv
```

2. Clone and install dependencies:

```bash
cd ~
git clone https://github.com/MsModig/mosmart.git
cd mosmart
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

3. Start from source:

```bash
sudo venv/bin/python3 web_monitor.py
```

## Verify installation

```bash
mosmart --help
mosmart-web --help
```

## Common issues

### Error: externally-managed-environment

Cause: System Python is protected by PEP 668.

Fix: Use `pipx install mosmart` or a virtual environment.

### Command not found: mosmart-web

1. Run `pipx ensurepath` again.
2. Open a new terminal.
3. Check install with `pipx list`.

### SMART permission errors

Run MoSMART with sudo when reading SMART data.

## Update and uninstall

Update:

```bash
pipx upgrade mosmart
```

Uninstall:

```bash
pipx uninstall mosmart
```
