# MoSMART - Dokumentasjon

## Innholdsfortegnelse
1. [Introduksjon](#introduksjon)
2. [Installasjon](#installasjon)
   - [Linux](#installasjon-linux)
   - [Windows (via WSL2)](#installasjon-windows-wsl2)
3. [Bruk av verktøyet](#bruk-av-verktøyet)
4. [Poengsystemet](#poengsystemet)
5. [Ghost Drive Condition (GDC)](#ghost-drive-condition-gdc)
6. [Varslingssystem](#varslingssystem)
7. [Vanlige spørsmål](#vanlige-spørsmål)

---

## Introduksjon

MoSMART er et omfattende overvåkningsverktøy for harddisker og SSD-er som leser og tolker S.M.A.R.T.-data (Self-Monitoring, Analysis and Reporting Technology). Programmet gir deg:

- **Sanntidsovervåking** av diskstatus og helse
- **Helsepoeng** (0-100) basert på kritiske parametere
- **Automatisk varsling** via e-post ved problemer
- **GDC-deteksjon** (Ghost Drive Condition) for frysende disker
- **Historikk** med grafer og trendanalyse
- **Moderne webgrensesnitt** tilgjengelig fra enhver nettleser

### Testing og Validering

MoSMART har blitt validert gjennom omfattende testing med **24 forskjellige lagringsenheter**:

- **Diverse disktyper:** SSD, SATA HDD og IDE (legacy) disker
- **Realistiske forhold:** Diskene har blitt brukt av forskjellige personer med varierende arbeidsbelastninger
- **Ulik slitasjegrad:** Fra praktisk talt nye disker til disker nær end-of-life
- **Virkelighetsjustering:** Testsettet reflekterer hvordan disker brukes i praksis - ikke kun laboratorietester

Denne testingen sikrer at programmet fungerer pålitelig på disker i alle tilstander og brukerscenarier.

---

## Installasjon

### Installasjon: Linux

#### Forutsetninger
- Ubuntu/Debian-basert Linux (20.04 eller nyere)
- Python 3.7 eller nyere
- Root/sudo-tilgang

#### Steg 1: Installer systemavhengigheter
```bash
sudo apt update
sudo apt install smartmontools python3-pip python3-venv git
```

#### Steg 2: Klon eller last ned prosjektet
```bash
cd ~
git clone <repository-url> mosmart
# Eller pakk ut zip-filen hvis du har lastet ned manuelt
```

#### Steg 3: Sett opp Python virtual environment
```bash
cd mosmart
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Steg 4: Start serveren
```bash
sudo ./venv/bin/python3 web_monitor.py
```

#### Steg 5: Åpne i nettleser
Gå til: `http://localhost:5000`

#### Kjøre i bakgrunnen (valgfritt)
For å kjøre serveren i bakgrunnen:
```bash
nohup sudo -b ./venv/bin/python3 web_monitor.py > /tmp/mosmart.log 2>&1
```

Stoppe serveren:
```bash
sudo pkill -f "web_monitor.py"
```

#### Auto-start ved systemoppstart (anbefalt)
For å få MoSMART til å starte automatisk når systemet booter:

1. Installer systemd-tjenesten:
```bash
cd ~/mosmart
sudo cp mosmart.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mosmart.service
```

2. Start tjenesten:
```bash
sudo systemctl start mosmart.service
```

3. Sjekk status:
```bash
sudo systemctl status mosmart.service
```

Nyttige kommandoer:
- `sudo systemctl stop mosmart` - Stopp tjeneste
- `sudo systemctl restart mosmart` - Restart tjeneste
- `sudo journalctl -u mosmart -f` - Se live logger
- `sudo systemctl disable mosmart` - Deaktiver auto-start

---

### Installasjon: Windows (WSL2)

⚠️ **MERK:** WSL2-støtten er basert på teoretisk implementering og er **IKKE testet** i praksis. Instruksjonene nedenfor gir veiledning, men funksjonalitet med SMART-lesing via WSL2 kan variere.

WSL2 (Windows Subsystem for Linux) lar deg kjøre Linux-programmer direkte i Windows.

#### Steg 1: Installer WSL2
Åpne PowerShell som Administrator og kjør:
```powershell
wsl --install
```

Dette installerer Ubuntu automatisk. Start datamaskinen på nytt når du får beskjed.

#### Steg 2: Sett opp Ubuntu
Første gang du starter Ubuntu, må du:
1. Velge brukernavn
2. Velge passord
3. Oppdatere systemet:
```bash
sudo apt update && sudo apt upgrade
```

#### Steg 3: Installer avhengigheter i WSL
```bash
sudo apt install smartmontools python3-pip python3-venv git
```

#### Steg 4: Kopier prosjektet til WSL
Fra Windows kan du kopiere filer til WSL:
```bash
# I WSL terminal:
cd ~
cp -r /mnt/c/Users/DittBrukernavn/Downloads/mosmart ~/mosmart
```

Eller klon direkte:
```bash
cd ~
git clone <repository-url> mosmart
```

#### Steg 5: Sett opp Python environment
```bash
cd ~/mosmart
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Steg 6: Start serveren
```bash
sudo ./venv/bin/python3 web_monitor.py
```

#### Steg 7: Åpne i Windows-nettleser
Selv om serveren kjører i WSL, er den tilgjengelig i Windows:
```
http://localhost:5000
```

#### Tips for Windows-brukere
- **Tilgang til WSL-filer fra Windows:** Åpne `\\wsl$\Ubuntu\home\brukernavn\mosmart` i Filutforsker
- **Start WSL:** Søk etter "Ubuntu" i Start-menyen
- **Auto-start ved oppstart:** Lag en oppgave i Windows Task Scheduler som kjører `wsl -d Ubuntu -u root /home/brukernavn/mosmart/start.sh`

---

## Bruk av verktøyet

### Hovedskjerm

Når du åpner `http://localhost:5000` ser du:

- **Device-kort** for hver disk med:
  - Modell og serienummer
  - Helsepoeng (0-100)
  - Temperatur
  - Driftstid
  - Kapasitet
  - Status-ikon (✅ OK, ⚠️ Warning, 🔴 Critical, 👻 GDC)

### Filtrer visning
- **Alle disker** - viser alt
- **Overvåkede** - kun disker som er satt til å overvåkes
- **Ikke overvåket** - disker du har skrudd av overvåking for
- **Med varsler** - disker med aktive problemer

### Vektlegging av poeng

**For HDD (harddisker):**
- Reallokerte sektorer: 35% - Defekte sektorer (løst problem)
- **Ventende sektorer: 25%** - Sektorer som feiler NÅ (aktiv fare)
- Power cycles: 10% - Antall av/på-sykluser (mekanisk slitasje)
- Urettbare sektorer: 10% - Permanent ødelagte sektorer
- Kommando timeouts: 10% - Responsivitetsproblemer
- Alder: 5% - Forventet levetid (3-5 år typisk)
- Temperatur: 5% - Driftstemperatur (<35°C ideelt)

**For SSD:**
- Reallokerte sektorer: 35-40% - Defekte blokker (løst problem)
- **Ventende sektorer: 25%** - Blokker som feiler NÅ (aktiv fare)
- Slitasjenivå: 0-15% - Basert på totalt skrevet data (når tilgjengelig)
- Temperatur: 10% - Driftstemperatur (<50°C ideelt)
- Urettbare sektorer: 5-10% - Permanent ødelagte blokker
- Kommando timeouts: 5-10% - Responsivitetsproblemer
- Alder: 2-5% - Forventet levetid (5-10 år typisk)

### tolkning av score:
- `95-100`: 🔵 UTMERKET - Perfekt stand
- `80-94`: 🟢 God - Normal drift
- `60-79`: 🟡 Akseptabel - Overvåk regelmessig
- `40-59`: 🟠 Advarsel - Sikre data med backup
- `20-39`: 🔴 Dårlig - Høy risiko
- `0-19`: 🔴 KRITISK - Bytt ut ASAP
- `<0`: 💀 DØD/ZOMBIE - Umiddelbar utskifting

### Force Scan
Klikk **"Force Scan"** øverst til høyre for å:
- Tvinge en full skanning av alle disker (inkludert GDC-disker)
- Oppdatere data umiddelbart
- Trigge varslingssystemet

### Per disk-handlinger

For hver disk har du knapper:

#### 📊 Details
Viser detaljert informasjon:
- Alle S.M.A.R.T.-attributter
- Nåværende verdier, terskelverdier, rådata
- Type attributt (Pre-fail/Old age)

#### 📈 History
Viser historiske grafer for:
- Helsepoeng over tid
- Temperatur over tid
- Kritiske attributter (reallocated sectors, pending sectors)
- Kan velge tidsperiode: 7, 30, 90, 180, 365 dager

#### 📝 View Log
Viser detaljert logg for disken:
- Når disk ble skannet
- Endringer i helsepoeng
- GDC-hendelser
- Varsler som er sendt

#### 👁️ Toggle Monitoring
Slår overvåking av/på for denne disken:
- **PÅ** (grønn): Disk blir skannet og varsler sendes
- **AV** (grå): Disk blir skannet, men ingen varsler

### Innstillinger ⚙️

Klikk tannhjulet øverst til høyre for å konfigurere:

#### General Settings
- **Refresh Interval:** Hvor ofte data oppdateres automatisk (sekunder)
- **Language:** Språk for grensesnittet (Norsk/English)

#### Health Alerts
- **Score Drop Threshold:** Hvor mye helsepoeng kan falle før varsel sendes
- **Critical Score:** Under denne scoren sendes kritisk varsel

#### Temperature Alerts
- **SSD Warning:** Temperaturgrense for advarsel (SSD)
- **SSD Critical:** Temperaturgrense for kritisk varsel (SSD)
- **HDD Warning:** Temperaturgrense for advarsel (HDD)
- **HDD Critical:** Temperaturgrense for kritisk varsel (HDD)
- **Consecutive Readings:** Hvor mange påfølgende målinger over grensen før varsel

#### Milestone Alerts
- **Reallocated Sectors:** Grenseverdier for reallokerte sektorer (f.eks. 1, 10, 50)
- **Pending Sectors:** Grenseverdier for ventende sektorer

#### Alert Channels (E-post)
- **SMTP Server:** Din e-postserver (f.eks. smtp.gmail.com)
- **SMTP Port:** Port (587 for TLS, 465 for SSL)
- **Username:** Din e-postadresse
- **Password:** App-passord (ikke vanlig passord!)
- **From Email:** Avsender-adresse
- **To Emails:** Mottaker(e), kommaseparert
- **Use TLS / Use STARTTLS:** Krypteringsinnstillinger

**Test E-mail:** Send en test-e-post for å verifisere at alt fungerer.

---

## Poengsystemet

Helsepoeng (0-100) beregnes ulikt for HDD og SSD basert på kritiske S.M.A.R.T.-parametere.

### For HDD (harddisker)

**Vekting av komponenter:**
- **Reallocated Sectors (35%):** Antall defekte sektorer som er erstattet
- **Pending Sectors (25%):** Sektorer som venter på å bli reallokert (aktiv fare)
- **Power Cycles (10%):** Antall av/på-sykluser (mekanisk slitasje)
- **Uncorrectable Errors (10%):** Feil som ikke kan rettes
- **Command Timeout (10%):** Kommandoer som timet ut
- **Age (5%):** Diskens alder basert på driftstimer
- **Temperature (5%):** Disktemperatur

**Scoring-logikk:**
```
Reallocated Sectors:
  0 sektorer = 100 poeng
  1-10 sektorer = 90 poeng
  11-100 sektorer = 70 poeng
  101-500 sektorer = 40 poeng
  501-1000 sektorer = 20 poeng
  1001-5000 sektorer = 5 poeng
  5001-10000 sektorer = -10 poeng
  10001-20000 sektorer = -50 poeng
  >20000 sektorer = -100 poeng (Zombie-disk)

Pending Sectors:
  0 = 100 poeng
  1 = 85 poeng
  2-5 = 60 poeng
  6-20 = 30 poeng
  21-100 = 10 poeng
  101-300 = -30 poeng
  301-500 = -70 poeng
  >500 = -100 poeng (Kritisk zombie)

Power Cycles:
  <1000 = 100 poeng (normal bruk)
  1000-5000 = 90 poeng (hyppige reboots)
  5000-10000 = 80 poeng (tung bruk)
  10000-20000 = 70 poeng
  20000-50000 = 50 poeng (veldig tung cycling)
  >50000 = 30 poeng (ekstrem bruk)

Temperature (HDD):
  <35°C = 100 poeng
  35-39°C = 90 poeng
  40-44°C = 70 poeng
  45-49°C = 40 poeng
  ≥50°C = 10 poeng

Uncorrectable Errors:
  0 = 100 poeng
  1 = 60 poeng (advarsel)
  2-5 = 20 poeng (alvorlig)
  6-10 = -30 poeng (kritisk)
  11-20 = -70 poeng (terminal)
  >20 = -100 poeng (zombie - permanent datatap)

Command Timeout:
  0 = 100 poeng
  1-5 = 70 poeng
  6-50 = 40 poeng
  51-200 = 20 poeng
  >200 = 0 poeng

Age (power-on hours):
  <17,520 timer (2 år) = 100 poeng
  17,520-26,280 timer (3 år) = 90 poeng
  26,280-43,800 timer (5 år) = 70 poeng
  43,800-61,320 timer (7 år) = 50 poeng
  61,320-87,600 timer (10 år) = 30 poeng
  >87,600 timer = 10 poeng
```

**Eksempel:** En HDD med 0 reallocated sectors (100p), 0 pending (100p), 1540 power cycles (90p), 25°C (100p), ingen errors (100p), ingen timeouts (100p), og 2.8 år gammel (90p):
```
Score = (100×0.35) + (100×0.25) + (90×0.10) + (100×0.10) + (100×0.10) + (90×0.05) + (100×0.05)
      = 35 + 25 + 9 + 10 + 10 + 4.5 + 5 = 98.5 poeng
```

### For SSD (solid state drives)

**Vekting uten wear-data:**
- **Reallocated Sectors (40%):** Defekte blokker
- **Pending Sectors (25%):** Ventende blokker (aktiv fare)
- **Temperature (10%):** SSD-temperatur
- **Uncorrectable Errors (10%):** Feil
- **Command Timeout (10%):** Timeouts
- **Age (5%):** Alder

**Vekting med wear-data (når bytes written er tilgjengelig):**
- **Reallocated Sectors (35%):** Redusert vekt
- **Pending Sectors (25%):** Kritisk vekt (aktiv fare)
- **Wear Level (15%):** Ny komponent basert på skrevne data
- **Temperature (10%):** Justert vekt
- **Uncorrectable Errors (8%):** Justert vekt
- **Command Timeout (5%):** Justert vekt
- **Age (2%):** Justert vekt

**Wear Level beregning:**
```
Bytes Written (LBAs × 512 eller Pages × 4096)
Rated Endurance (avhenger av modell og størrelse)

Eksempel: CT480BX500SSD1 (480GB SSD)
  Rated: ~96 TB (basert på typisk TBW for budsjett-SSD)
  Skrevet: 7 TB
  Wear: 7/96 = 7.3%
  Score: 100 - (7.3 × 1.5) = ~89 poeng

Over 100% wear = 0 poeng
```

**Temperatur for SSD:**
- Optimal: <50°C
- Høy: 50-70°C (lineær nedgang)
- Kritisk: >70°C

### Lifetime Remaining (SMART ID 202)

Moderne SSD-er rapporterer gjenstående levetid via SMART ID 202 (Percent_Lifetime_Remaining):

**Visning:**
- **>10%:** Vises inline med andre data
- **≤10%:** Vises som separat advarsel (gul eller rød)
- **≤5%:** Kritisk advarsel med anbefaling om utskifting

**Penalty-scoring:**
```
Lifetime Remaining → Health Score straff
  ≤5%:  -35 poeng (KRITISK)
  6%:   -20 poeng
  7%:   -17 poeng
  8%:   -14 poeng
  9%:   -11 poeng
  10%:  -10 poeng
  11-20%: Lineær nedgang (-0.5 per %)
  ≥21%: 0 straff (ingen bekymring)
```

**Tooltips:**
- **≤10%:** "Gjenstående levetid er kritisk lav – bytt disk snarest"
- **≤20%:** "Gjenstående levetid er lav – planlegg utskifting snart"
- **>20%:** "SMART ID 202 viser gjenstående levetid i prosent"

---

## Tekniske forbedringer

### Thread-safe Scanning (2026)

MoSMART bruker thread-safe locking for alle scanning-operasjoner:

**Funksjoner:**
- **Atomic updates:** Placeholder-data overskrives aldri av gammel data
- **Race condition-beskyttelse:** Threading.Lock() på alle scan_results-tilganger
- **Watchdog-overvåking:** Automatisk deteksjon av stuck devices (30 sekunders timeout)
- **Lifecycle logging:** Logger stuck devices til `~/.mosmart/device_events/lifecycle.jsonl`

**Implementasjon:**
```python
# Thread-safe placeholder initialization
set_scan_result_placeholder(device_name)

# Thread-safe atomic update with collision protection
update_scan_result(device_name, device_data)

# Thread-safe bulk read for API
devices = get_all_scan_results()
```

**Watchdog:**
- Kjøres hver 60. sekund i background_scanner
- Logger devices stuck i "⏳ Scanning..." >30 sekunder
- Forhindrer permanent UI-hang på problematiske USB-disker

### Windows-støtte via WSL2

MoSMART fungerer fullt på Windows 10/11 via WSL2 (Windows Subsystem for Linux):

**Fordeler:**
- Full Linux-funksjonalitet inne i Windows
- Dashboard tilgjengelig på `http://localhost:5000` i Windows-nettleser
- Tilgang til WSL-filer via `\\wsl$\Ubuntu\home\brukernavn\mosmart` i Filutforsker
- Automatisk oppstart mulig via Windows Task Scheduler

**Begrensninger:**
- Kun Linux-disker innenfor WSL synlige (ikke native Windows-disker)
- Krever WSL2 (ikke WSL1)
- Se [Installasjon: Windows (WSL2)](#installasjon-windows-wsl2) for oppsettguide

---

## Ghost Drive Condition (GDC)

GDC er en tilstand der en disk "fryser" eller blir ustabil, ofte på grunn av hardware-problemer.

### Deteksjon

Systemet overvåker flere indikatorer:

1. **Timeouts:** Disk svarer ikke innen timeout-perioden
2. **Feil JSON:** pySMART returnerer korrupte data
3. **Disappeared:** Disk forsvinner fra system
4. **Corrupt data:** S.M.A.R.T.-data er inkonsistente

### GDC States

Disker går gjennom ulike tilstander:

```
OK → SUSPECT → PROBABLE → CONFIRMED → TERMINAL
```

**OK:** Disk fungerer normalt
- Alle forespørsler går gjennom
- Ingen unormale timeouts

**SUSPECT:** Første tegn på problemer
- 3-5 påfølgende timeouts
- Blir satt tilbake til OK ved én vellykket lesing

**PROBABLE:** Sannsynlig GDC
- 6-9 påfølgende timeouts
- Krever 2 vellykkede lesinger for å gå tilbake til OK

**CONFIRMED:** Bekreftet GDC
- 10+ påfølgende timeouts
- Disk blir **ikke** skannet automatisk (spart ressurser)
- Krever 3 vellykkede lesinger for å gå tilbake

**TERMINAL:** Permanent død disk
- 50+ påfølgende timeouts uten noen vellykkede lesinger
- Disk ignoreres fullstendig

### GDC Freeze Mode

Når du klikker **Force Scan**, settes alle GDC-disker i "freeze mode" i 5 minutter:
- State settes midlertidig til OK
- Disk blir skannet på nytt
- Gir deg mulighet til å se om disk er tilbake

### Historikk

Systemet logger alle GDC-hendelser:
- Når disk gikk inn i hvilken state
- Totalt antall timeouts/errors
- Mønster av feil (siste 10 hendelser)

Du kan se dette i **View Log** for disken.

---

## Varslingssystem

### Typer varsler

#### 1. Health Score Alerts
- **Score Drop:** Sendes når helsepoeng faller med X poeng siden forrige skanning
- **Critical Score:** Sendes når helsepoeng går under kritisk grense

#### 2. Temperature Alerts
- **Warning:** Disk når warning-temperatur
- **Critical:** Disk når kritisk temperatur
- **Normalized:** Disk er tilbake til normal temperatur

**Consecutive Readings:** Krever at temperaturen er over grense i X påfølgende skanninger før varsel sendes (unngår falske alarmer).

#### 3. Milestone Alerts
- **Reallocated Sectors:** Sendes når antallet krysser en grenseverdi (f.eks. 1, 10, 50)
- **Pending Sectors:** Sendes når antallet krysser en grenseverdi

#### 4. GDC Alerts
- **State Change:** Sendes når disk endrer GDC-tilstand
- **Confirmed GDC:** Kritisk varsel når disk bekreftes som GDC

### E-postvarsler

**Opsett:**
1. Gå til Innstillinger → Alert Channels
2. Fyll inn SMTP-detaljer
3. **Viktig:** Bruk app-passord, ikke vanlig passord!

**Gmail-eksempel:**
- SMTP Server: `smtp.gmail.com`
- Port: `587`
- Use TLS: `✓`
- Username: `din@gmail.com`
- Password: [App-passord fra Google](https://myaccount.google.com/apppasswords)

**E-postformat:**
```
Subject: [MoSMART] Critical Alert: sda Health Score

Device: CT480BX500SSD1 (sda)
Alert Type: CRITICAL_SCORE
Severity: HIGH

Health score critically low: 35 (threshold: 40)

Timestamp: 2025-12-02 10:30:15
```

### Varsel-historikk

Alle sendte varsler logges og kan sees i **View Log** for hver disk.

---

## Vanlige spørsmål

### Hvorfor trenger programmet sudo/root?
S.M.A.R.T.-data krever direkte tilgang til disk-hardware, noe som kun er tillatt for root-brukere.

### Kan jeg kjøre dette på en server uten skjerm?
Ja! Webgrensesnittet kan nås fra enhver datamaskin på nettverket. Bare sørg for at port 5000 er åpen.

### Hvor ofte skal jeg skanne diskene?
Standard er 300 sekunder (5 minutter). Dette er en god balanse mellom oppdatert data og disk-slitasje.

### Hva betyr de ulike S.M.A.R.T.-attributtene?
- **005 Reallocated Sectors:** Defekte sektorer som er erstattet
- **196 Reallocation Events:** Antall ganger reallokering har skjedd
- **197 Current Pending Sector:** Sektorer som venter på å bli testet/reallokert
- **198 Uncorrectable Sector:** Sektorer som ikke kan leses/skrives
- **199 UltraDMA CRC Errors:** Datafeil under overføring
- **194 Temperature:** Disktemperatur i Celsius

### Hvordan tolker jeg helsepoeng?
- **90-100:** Utmerket - disk er i topp stand
- **70-89:** God - disk fungerer normalt
- **50-69:** Akseptabel - hold øye med disk
- **30-49:** Dårlig - backup data snart!
- **0-29:** Kritisk - bytt disk umiddelbart

### Hva er "Bytes Written" på SSD?
Dette viser totalt antall data skrevet til SSD-en over dens levetid. Sammen med rated endurance (TBW) gir dette et mål på "slitasje".

Eksempel: 7 TB skrevet av 96 TB rated = 7.3% slitasje = utmerket!

### Kan jeg overvåke disker i en RAID?
Ja, men du ser individuelle disker, ikke RAID-arrayet som helhet. Hver disk overvåkes separat.

### Hvordan stopper jeg varsler fra en disk?
Klikk **"Toggle Monitoring"** på disk-kortet. Disken blir fortsatt skannet, men sender ingen varsler.

### Hva skjer hvis en disk får GDC?
1. Disk merkes som CONFIRMED
2. Disk blir ikke lenger automatisk skannet (spart ressurser)
3. Du kan tvinge skanning med "Force Scan"
4. Hvis disk kommer tilbake, går den gradvis tilbake til OK-status

### Hvor lagres data?
- **Konfigurasjon:** `~/.mosmart/settings.json`
- **Historikk:** `~/.mosmart/history/<model>_<serial>.json`
- **GDC-logger:** `~/.mosmart/gdc_events/<device>.json`
- **Alert-logger:** `~/.mosmart/alerts/<model>_<serial>.json`
- **Disk-logger:** `~/.mosmart/disk_logs/<model>_<serial>.log`

### Kan jeg kjøre dette på flere datamaskiner?
Ja! Bare installer på hver maskin. Hver installasjon overvåker sine egne disker.

### Støtter systemet NVMe-disker?
Ja, hvis smartmontools og pySMART støtter dem på ditt system. De fleste moderne NVMe-disker støttes.

### Hva gjør "Force Scan"?
- Tvinger full skanning av alle disker (inkludert GDC)
- Setter GDC-disker i "freeze mode" i 5 minutter
- Trigger varslingssystemet umiddelbart
- Oppdaterer all data

---

## Support og feilsøking

### Serveren starter ikke
```bash
# Sjekk om port 5000 er opptatt
sudo lsof -i :5000

# Sjekk logger
tail -f /tmp/mosmart.log

# Sjekk at alle avhengigheter er installert
./venv/bin/pip list
```

### Ingen data vises
- Sjekk at du kjører med sudo
- Sjekk at smartmontools er installert: `smartctl --version`
- Sjekk at disker er synlige: `sudo smartctl --scan`

### E-post fungerer ikke
- Test SMTP-innstillinger med "Test E-mail"-knappen
- Sjekk at du bruker app-passord, ikke vanlig passord
- Sjekk at port 587/465 ikke er blokkert av brannmur

### GDC falskt positivt
Hvis en disk feilaktig merkes som GDC:
1. Klikk "Force Scan"
2. Hvis disk svarer, vil GDC-status gradvis normaliseres
3. Sjekk kabler og strømforsyning

---

**Versjon:** 0.9 beta  
**Sist oppdatert:** 2. februar 2026  
**Laget av:** Magnus S. Modig med hjelp fra GitHub Copilot
