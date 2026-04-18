# MoSMART - S.M.A.R.T. Monitor

A Python-based tool for reading and interpreting S.M.A.R.T. (Self-Monitoring, Analysis and Reporting Technology) data from hard drives on Linux systems.

> 🇳🇴 [Norsk dokumentasjon](dokumentasjon-no.md) | 🇬🇧 [Full English Documentation](documentation-en.md)

## 🚀 Quick Installation

```bash
sudo apt update
sudo apt install smartmontools python3-full pipx
pipx ensurepath
pipx install mosmart
sudo mosmart
```

Open **http://localhost:5000** in your browser.

## Distro-spesifikke guider

- Linux Mint: [INSTALL_LINUX_MINT.md](INSTALL_LINUX_MINT.md)
- Debian: [INSTALL_DEBIAN.md](INSTALL_DEBIAN.md)
- Ubuntu: [INSTALL_UBUNTU.md](INSTALL_UBUNTU.md)

## Hvilken installasjonsmetode bør jeg velge?

| Metode | Passer best for | Fordeler | Merknad |
|--------|------------------|----------|---------|
| `pipx install mosmart` | De fleste brukere | Enkelt, isolert, PEP 668-sikkert | Anbefalt på Linux Mint/Debian/Ubuntu |
| Kildekode + `venv` | Utvikling og tilpasning | Full kontroll over kildekode og avhengigheter | Kjør fra repo med `venv/bin/python3` |
| `install.sh` | Systemtjeneste på maskiner/servere | Integrasjon med systemd | Best for dedikerte verter/servere |

## Funksjoner

- 📊 Skann og vis alle tilgjengelige lagringsenheter
- 🔍 Les detaljerte S.M.A.R.T. attributter
- ⚠️ Oppdage potensielle helseproblemer
- 🌡️ Overvåk disktemperatur
- 📈 Vis kritiske parametre som reallokerte sektorer, strømtid, og mer
- 🧠 **Health Score System** - Intelligent poengberegning (0-100) basert på kritiske parametere
- 🌐 **Web Dashboard** - Moderne web-grensesnitt for sanntidsovervåking
- ⚙️ Konfigurerbar auto-refresh og individuell disk-monitoring
- �️ **Emergency Unmount** - Automatisk fjerning av kritisk feilende disker (valgfritt)
- ⌛ **Lifetime Remaining** - SMART ID 202 støtte for SSD-slitasjemåling
- 🔒 **Thread-safe Scanning** - Race condition-beskyttelse med watchdog-overvåking
- 💻 Støtte for Linux og ⚠️ **Windows (via WSL2 - teoretisk, ikke testet)**

## Testing og Validering

MoSMART har blitt validert gjennom omfattende testing med **24 forskjellige lagringsenheter**:

- **Diverse disktyper:** SSD, SATA HDD og IDE (legacy) disker
- **Realistiske forhold:** Diskene har blitt brukt av forskjellige personer med varierende arbeidsbelastninger
- **Ulik slitasjegrad:** Fra praktisk talt nye disker til disker nær end-of-life
- **Virkelighetsjustering:** Testsettet reflekterer hvordan disker brukes i praksis - ikke kun laboratorietester

Denne testingen sikrer at programmet fungerer pålitelig på disker i alle tilstander og brukerscenarier.

## Krav

### Systemkrav
- Linux-operativsystem
- Python 3.7 eller nyere
- `smartmontools` installert på systemet
- Root/sudo-tilgang for å lese S.M.A.R.T. data

### Installasjon av systemavhengigheter

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install smartmontools python3-pip python3-venv

# Fedora/RHEL
sudo dnf install smartmontools python3-pip

# Arch Linux
sudo pacman -S smartmontools python-pip
```

## Installasjon

### Installer via PyPI (anbefalt)

```bash
sudo apt update
sudo apt install smartmontools python3-full pipx
pipx ensurepath
pipx install mosmart
```

**Kjør web-dashboardet:**
```bash
sudo mosmart
```

1. **Installer systemavhengigheter**
   ```bash
   sudo apt update
   sudo apt install smartmontools python3-full python3-pip pipx
   ```

2. **Installer med pipx (anbefalt for enkeltstående verktøy)**
   ```bash
  pipx install mosmart
   ```

   **ELLER opprett et virtuelt miljø:**
   ```bash
  cd /path/to/mosmart
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

   Når du bruker virtuelt miljø, aktiver det før bruk:
   ```bash
   source venv/bin/activate
   ```

## Quick Start (PyPI)

```bash
pipx install mosmart
sudo mosmart
```

Åpne deretter nettleseren din og gå til: **http://localhost:5000**

## Bruk

> **Viktig:** Hvis du bruker virtuelt miljø, aktiver det først: `source venv/bin/activate`

### Web Dashboard (Anbefalt!)

**Start web-serveren:**
```bash
sudo ./venv/bin/python3 web_monitor.py
```

**Med egendefinert port:**
```bash
sudo ./venv/bin/python3 web_monitor.py --port 8080
```

**Med egendefinert refresh-intervall:**
```bash
sudo ./venv/bin/python3 web_monitor.py --refresh 30
```

Åpne deretter nettleseren din og gå til: **http://localhost:5000**

**Web Dashboard funksjoner:**
- 🎨 Moderne, fargekodet visning av alle disker
- 🔄 Auto-refresh (konfigurerbar, standard 60 sek)
- ⏯️ Slå av/på overvåking per disk
- 📊 Sanntidsoppdatering av health scores
- 🎯 Detaljert visning av alle helsekomponenter
- 📱 Responsiv design for mobil og desktop

### Kommandolinje (CLI)

**Liste alle lagringsenheter:**
```bash
sudo ./venv/bin/python3 smart_monitor.py --list
```

**Vis informasjon om en spesifikk disk:**
```bash
sudo ./venv/bin/python3 smart_monitor.py -d /dev/sda
```

**Vis detaljerte S.M.A.R.T. attributter:**
```bash
sudo ./venv/bin/python3 smart_monitor.py -d /dev/sda --attributes
```

**Kun helseoppsummering:**
```bash
sudo ./venv/bin/python3 smart_monitor.py -d /dev/sda --health
```

**Skann alle disker:**
```bash
sudo ./venv/bin/python3 smart_monitor.py
```

### Kommandolinjealternativer (CLI)

**smart_monitor.py:**
```
-l, --list          Liste alle tilgjengelige lagringsenheter
-d, --device PATH   Spesifiser hvilken enhet som skal overvåkes (f.eks. /dev/sda)
-a, --attributes    Vis detaljerte S.M.A.R.T. attributter
--health            Vis kun helseoppsummering
```

**web_monitor.py:**
```
-p, --port PORT     Port for webserver (default: 5000)
-r, --refresh SEC   Auto-refresh intervall i sekunder (default: 60)
--host HOST         Host å binde til (default: 127.0.0.1)
```

## Health Score System

Programmet bruker et avansert poengberegningssystem basert på industristandarder fra Backblaze, Google og diskprodusenter:

**Vekting:**
- **Reallokerte sektorer: 50%** - Mest kritisk parameter
- **Ventende sektorer: 15%** - Sektorer som venter på reallokering
- **Urettbare sektorer: 10%** - Permanent ødelagte sektorer
- **Kommando timeouts: 10%** - Responsivitetsproblemer
- **Alder: 10%** - Forventet levetid (HDD: 3-5 år, SSD: 5-10 år)
- **Temperatur: 5%** - Driftstemperatur (HDD: <35°C ideelt, SSD: <40°C)

**Score-tolkning:**
- `95-100`: 🔵 UTMERKET - Perfekt stand
- `80-94`: 🟢 God - Normal drift
- `60-79`: 🟡 Akseptabel - Overvåk regelmessig
- `40-59`: 🟠 Advarsel - Sikre data med backup
- `20-39`: 🔴 Dårlig - Høy risiko
- `0-19`: 🔴 KRITISK - Bytt ut ASAP
- `<0`: 💀 DØD/ZOMBIE - Umiddelbar utskifting

## Eksempel på output

```
============================================================
Device: /dev/sda
============================================================
Model:        Samsung SSD 870 EVO 500GB
Serial:       S5XXXXXXXX
Capacity:     500.107 GB
Interface:    ATA
Assessment:   PASS
Temperature:  35°C
Power On:     1234 hours

Health Summary:
Status: PASS
✓ No issues detected
```

## Viktighelse S.M.A.R.T. attributter

Programmet overvåker spesielt disse kritiske attributtene:

- **ID 5**: Reallocated Sectors Count - Antall defekte sektorer som er flyttet
- **ID 187**: Reported Uncorrectable Errors - Feil som ikke kunne rettes
- **ID 196**: Reallocation Event Count - Antall forsøk på å flytte sektorer
- **ID 197**: Current Pending Sector Count - Sektorer som venter på reallokering
- **ID 198**: Uncorrectable Sector Count - Antall sektorer med urettbare feil
- **ID 202**: Percent Lifetime Remaining - SSD-slitasje (0-100%, lavere er dårligere)

## Tekniske forbedringer

### Thread-safe Scanning
MoSMART bruker thread-safe locking for alle scan-operasjoner:
- **Atomic updates** - Placeholder-data overskrives aldri av gammel data
- **Race condition-beskyttelse** - Locking på alle scan_results-tilganger
- **Watchdog-overvåking** - Detekterer stuck devices automatisk (30s timeout)
- **Lifecycle logging** - Logger stuck devices for feilsøking

### Lifetime Remaining (SMART ID 202)
Støtte for SMART ID 202 (Percent_Lifetime_Remaining) på moderne SSD-er:
- **Display** - Vises inline hvis >10%, separat hvis ≤10%
- **Penalty scoring** - Eksponentiell straff ved lav verdi:
  - ≤5%: -35 poeng (kritisk)
  - 6-10%: -20 til -10 poeng (advarsel)
  - 11-20%: Lineær nedgang
  - ≥21%: Ingen straff
- **Tooltips** - Kontekstavhengige meldinger for brukerveiledning

### Windows-støtte (WSL2)
MoSMART fungerer fullt på Windows via WSL2 (Windows Subsystem for Linux):
- **Full funksjonalitet** - Alle features tilgjengelig
- **Enkel tilgang** - Dashboard tilgjengelig fra Windows-nettleser
- **Filintegrasjon** - WSL-filer tilgjengelige via `\\wsl$\` i Filutforsker
- Se [Installasjon](#installasjon) for komplett WSL2-guide

## Feilsøking

### "Permission denied" feil
S.M.A.R.T. data krever root-tilgang. Kjør programmet med `sudo`:
```bash
sudo python3 smart_monitor.py -d /dev/sda
```

### "Command not found: smartctl"
Installer smartmontools:
```bash
sudo apt install smartmontools
```

### "No module named 'pySMART'"
Installer Python-avhengigheter i et virtuelt miljø:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### "externally-managed-environment" feil
Dette er normalt på nyere Linux Mint/Debian/Ubuntu-systemer (PEP 668).

Anbefalt løsning for app-installasjon:
```bash
sudo apt install pipx python3-full
pipx ensurepath
pipx install mosmart
```

Alternativt kan du bruke virtuelt miljø:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Virtuelt miljø ikke tilgjengelig
Installer python3-full:
```bash
sudo apt install python3-full
```

## Emergency Unmount

MoSMART kan automatisk fjerne kritisk feilende disker fra systemet for å forhindre datakorrupsjon.

**Default: PASSIVE modus (trygt)**
- Evaluerer disk-helse
- Logger beslutninger
- Ingen automatiske handlinger

**Aktivere ACTIVE modus (valgfritt):**
```bash
# 1. Rediger config
nano ~/.mosmart/settings.json

# 2. Sett mode til ACTIVE
{
  "emergency_unmount": {
    "mode": "ACTIVE"
  }
}

# 3. Restart service
sudo systemctl restart mosmart
```

**Sikkerhet:**
- ✅ Aldri unmount kritiske stier (/, /boot, /home)
- ✅ 30 minutters cooldown mellom forsøk
- ✅ Full logging før/under/etter
- ✅ Default til PASSIVE ved config-feil

Se [EMERGENCY_UNMOUNT_IMPLEMENTATION.md](EMERGENCY_UNMOUNT_IMPLEMENTATION.md) for detaljer.

## Lisens

**MoSMART Monitor** bruker en delt lisensmodell for maksimal kontroll og åpenhet:

### 📜 Kode - GNU General Public License v3.0 (GPLv3)

All Python-kode og JavaScript-kode er lisensiert under GPLv3. Dette betyr:
- ✅ Du kan bruke, endre og dele koden
- ✅ Du må dele dine endringer under samme lisens
- ✅ Du må inkludere LICENSE-fil og copyright-notis

Se [LICENSE](LICENSE) fil for fullstendig tekst.

### 🎨 Logo & Design - All Rights Reserved

De følgende ressurser er **IKKE** dekket av GPLv3:

- **modig-logo-monokrom.png** - MoSMART Monitor logo
- **logo-top.svg** - Modigs Datahjelp logo  
- Alle UI/UX design-elementer og visuell identitet

© Magnus S. Modig / Modigs Datahjelp – **All Rights Reserved**

Disse kan IKKE brukes, reproduseres eller modifiseres uten eksplisitt tillatelse.

### 📚 Dokumentasjon - Creative Commons BY-SA 4.0

All dokumentasjon er lisensiert under CC BY-SA 4.0:

- README.md
- dokumentasjon-no.md
- documentation-en.md
- PASSIVE_MODE_README.md
- EMERGENCY_UNMOUNT_IMPLEMENTATION.md
- Alle andre .md-dokumentasjonsfiler

Du kan dele og tilpasse dokumentasjonen med attribusjon.

### ℹ️ Se også

Se [COPYRIGHT](COPYRIGHT) fil for fullstendig lisens- og branding-informasjon.

## Bidrag

Bidrag er velkomne! Vennligst åpne en issue eller pull request.

## Advarsel

⚠️ Dette verktøyet er laget for informasjonsformål. Ta alltid backup av viktige data, og konsulter med en profesjonell ved tegn på diskfeil.
