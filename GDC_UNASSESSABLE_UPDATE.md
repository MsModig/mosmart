# GDC Unassessable Update - 3. januar 2026

## Mål
Justere GDC-detektering slik at manglende SMART-data ALDRI kan trigge GDC.

## Viktig prinsipp
**NULL = ingen data, 0 = data, ustabile data = mulig diskfeil**

> "Missing SMART data is not disk failure. GDC is triggered by lying data, not missing data."

## Endringer

### 1. Ny tilstand: UNASSESSABLE
Lagt til `GDCState.UNASSESSABLE` i `gdc.py`:
- Representerer enheter uten SMART-støtte (USB-adaptere, ikke-SMART disker)
- Skilles eksplisitt fra GDC-tilstander (SUSPECT, CONFIRMED, TERMINAL)
- Vises i GUI som informasjon, ikke som feil

### 2. Ny metode: event_no_smart_support()
`GDCManager.event_no_smart_support()` i `gdc.py`:
- Kalles når en enhet bekreftes å mangle SMART-støtte
- Setter `smart_supported = False`
- Setter tilstand til `UNASSESSABLE` (permanent for denne sesjonen)
- Trigger IKKE GDC-evaluering

### 3. Oppdatert GDC-evalueringslogikk
`GDCManager._evaluate()` i `gdc.py`:
- Respekterer `UNASSESSABLE` tilstand (ikke overskriver den)
- Krever bevis for ustabilitet før GDC trigges
- Skiller mellom:
  - **Manglende data** → UNASSESSABLE (ingen SMART-støtte)
  - **Ustabile data** → GDC (har SMART, men lyver)
  - **Null data** → UNASSESSABLE (første scan, ingen historikk)
  - **0-verdi** → Gyldig datapunkt (evalueres normalt)

### 4. Smart deteksjon i web_monitor.py
`scan_all_devices_progressive()` i `web_monitor.py`:
- Sjekker om enhet er USB (`is_usb`)
- Sjekker om enhet mangler modell/serienummer konsistent
- Kaller `event_no_smart_support()` for USB eller enheter uten identitet
- Kaller `event_no_json()` kun for enheter som SKAL ha SMART

### 5. GUI-oppdateringer

#### JavaScript (`static/main_new.js`):
- `getDeviceStatus()`: Håndterer `UNASSESSABLE` som egen status
- `renderDeviceCard()`: Viser ℹ️-ikon og info-melding for UNASSESSABLE

#### CSS (`static/datasmart_new.css`):
- `.status-unassessable`: Grå border og bakgrunn (ikke kritisk)
- `.unassessable-warning`: Grå tekst (informasjon, ikke advarsel)
- `.status-badge.unassessable`: Grå badge styling
- `.unassessable-icon`: Info-ikon med soft glow

#### Oversettelser (`translations.json`):
- `unassessable_smart_data` (NO): "SMART-data ikke tilgjengelig - kan ikke vurdere diskhelse"
- `unassessable_smart_data` (EN): "SMART data not available - cannot assess disk health"
- `unassessable` (NO): "Ikke vurderbar"
- `unassessable` (EN): "Unassessable"

## Tilstands-diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Scan Enhet                                                  │
└───────────────────┬─────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
    USB eller                Intern disk
    ingen ID?                med ID?
        │                       │
        ▼                       ▼
  UNASSESSABLE          Har SMART-data?
  (permanent)                  │
                    ┌──────────┴──────────┐
                    │                     │
                  Ja, OK              Nei, timeout
                    │                     │
                    ▼                     ▼
               event_success()      event_no_json()
                    │                     │
                    ▼                     ▼
                   OK              Evaluering:
                                   - 3+ fails → SUSPECT
                                   - 5+ fails → CONFIRMED
                                   - 8+ fails → TERMINAL
```

## Eksempler

### USB-disk (før endring):
```
Scan 1: no_json → timeout_count=1
Scan 2: no_json → timeout_count=2
Scan 3: no_json → timeout_count=3 → GDC CONFIRMED ❌
```

### USB-disk (etter endring):
```
Scan 1: is_usb=true → event_no_smart_support() → UNASSESSABLE ✅
Scan 2: UNASSESSABLE (ingen endring)
Scan 3: UNASSESSABLE (ingen endring)
```

### Faktisk GDC (fungerer fortsatt):
```
Scan 1: success → OK
Scan 2: success → OK
Scan 3: timeout → SUSPECT
Scan 4: timeout → SUSPECT
Scan 5: timeout → CONFIRMED
```

## Testing
Se [test_passive_mode.py](test_passive_mode.py) for testing av GDC-logikk.

```bash
sudo python3 test_passive_mode.py
```

## Kompatibilitet
- ✅ Eksisterende funksjonalitet bevart
- ✅ GDC-deteksjon for faktiske dårlige disker fungerer fortsatt
- ✅ USB-disker får nå UNASSESSABLE i stedet for falsk GDC
- ✅ GUI viser tydelig forskjell mellom GDC (💀 rød) og UNASSESSABLE (ℹ️ grå)
- ✅ Ingen breaking changes i API eller loggformat

## Videre arbeid
- [ ] Overvåke at UNASSESSABLE fungerer som forventet i produksjon
- [ ] Vurdere om UNASSESSABLE skal vises i e-postvarslinger
- [ ] Eventuelt legge til logging av UNASSESSABLE-beslutninger
