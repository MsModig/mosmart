# MoSMART Installation Guide for Ubuntu

This guide is for Ubuntu systems (Desktop or Server).

## Why pip install may fail

Ubuntu follows PEP 668 on newer releases.
Direct installation with system pip can return
`externally-managed-environment`.

Use pipx or virtual environments instead.

## Recommended method: pipx

1. Install dependencies:

```bash
sudo apt update
sudo apt install -y smartmontools python3-full pipx
```

2. Configure pipx path:

```bash
pipx ensurepath
```

3. Open a new terminal and install MoSMART:

```bash
pipx install mosmart
```

4. Start MoSMART web dashboard:

```bash
sudo env "PATH=$PATH" mosmart-web
```

5. Open browser:

http://localhost:5000

## Alternative method: source + venv

1. Install prerequisites:

```bash
sudo apt update
sudo apt install -y git smartmontools python3-full python3-venv
```

2. Clone and set up environment:

```bash
cd ~
git clone https://github.com/MsModig/mosmart.git
cd mosmart
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

3. Run MoSMART:

```bash
sudo venv/bin/python3 web_monitor.py
```

## Verify

```bash
mosmart --help
mosmart-web --help
```

## Common fixes

### externally-managed-environment

Expected on modern Ubuntu. Use pipx or venv.

### mosmart-web not found

Run `pipx ensurepath`, then open a new terminal.

### Permission denied reading SMART

Run MoSMART commands with sudo.

## Update or uninstall

Update:

```bash
pipx upgrade mosmart
```

Uninstall:

```bash
pipx uninstall mosmart
```
