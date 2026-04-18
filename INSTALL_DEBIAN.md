# MoSMART Installation Guide for Debian

This guide is for Debian systems using apt and Python 3.

## Important note about pip on Debian

On newer Debian versions, direct `pip install` to system Python may fail with
`externally-managed-environment` (PEP 668).

This is expected and protects system packages.

## Recommended method: pipx

1. Install system dependencies:

```bash
sudo apt update
sudo apt install -y smartmontools python3-full pipx
```

2. Enable pipx path:

```bash
pipx ensurepath
```

3. Open a new terminal and install MoSMART:

```bash
pipx install mosmart
```

4. Start MoSMART:

```bash
sudo env "PATH=$PATH" mosmart-web
```

5. Open dashboard:

http://localhost:5000

## Alternative method: virtual environment from source

1. Install prerequisites:

```bash
sudo apt update
sudo apt install -y git smartmontools python3-full python3-venv
```

2. Clone and install:

```bash
cd ~
git clone https://github.com/MsModig/mosmart.git
cd mosmart
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

3. Start:

```bash
sudo venv/bin/python3 web_monitor.py
```

## Verification

```bash
mosmart --help
mosmart-web --help
```

## Troubleshooting

### externally-managed-environment

Use `pipx install mosmart` or `python3 -m venv venv`.

### smartctl not found

Install smartmontools:

```bash
sudo apt install -y smartmontools
```

### Could not connect to dashboard

Check service output and verify port 5000 is free.

## Update and removal

Update:

```bash
pipx upgrade mosmart
```

Remove:

```bash
pipx uninstall mosmart
```
