# Språkfiler for MoSMART Monitor

## Legge til et nytt språk

For å legge til støtte for et nytt språk, følg disse trinnene:

### Trinn 1: Kopier malen

```bash
cp template.lang ditt_språk.lang
```

For eksempel:
- `german.lang`
- `french.lang`
- `spanish.lang`

### Trinn 2: Rediger filen

Åpne din nye `.lang`-fil og oppdater disse feltene:

1. **language_name**: Navnet på morsmålet (f.eks. "Deutsch", "Français")
2. **language_code**: ISO 639-1 to-bokstavskode (f.eks. "de", "fr")
3. **translations**: Oversett hver verdi

#### Eksempel (Tysk):
```json
{
    "language_name": "Deutsch",
    "language_code": "de",
    "translations": {
        "refresh_now": "Jetzt aktualisieren",
        "force_scan": "Scan erzwingen",
        "settings": "Einstellungen",
        ...
    }
}
```

### Trinn 3: Test oversettelsen

1. **Lagre** `.lang`-filen i `languages/` mappen
2. **Start serveren på nytt**:
   ```bash
   sudo pkill -f "web_monitor.py"
   sudo ./venv/bin/python3 web_monitor.py
   ```
3. **Åpne** webgrensesnittet: `http://localhost:5000`
4. **Gå til** Innstillinger ⚙️ → Generelle innstillinger
5. **Velg** ditt språk fra nedtrekksmenyen
6. **Verifiser** at all tekst er korrekt oversatt

### Oversettingstips

- **Vær konsekvent**: Bruk samme terminologi gjennomgående
- **Hold det kort**: Noen etiketter vises i knapper eller små rom
- **Test grundig**: Sjekk alle faner i Innstillinger, alle knapper, alle modaler
- **Tekniske termer**: "SMART", "GDC", "SSD", "HDD" oversettes vanligvis ikke
- **Enheter**: Behold temperaturenheter (°C), tidsenheter i vanlig form

### Komplette oversettelsesnøkler

Se `english.lang` for komplett liste over alle 66 oversettelsesnøkler. Alle nøkler må være til stede i din fil.

### Filformat

- **Format**: JSON
- **Encoding**: UTF-8
- **Navn**: `<språk_på_engelsk>.lang` (små bokstaver)

### Nåværende språk

- 🇳🇴 **Norsk** (no) - `norwegian.lang`
- 🇬🇧 **Engelsk** (en) - `english.lang`

---

**Auto-deteksjon:** Systemet skanner automatisk denne mappen etter `*.lang`-filer ved oppstart. Ingen kodeendringer nødvendig!

**Versjon:** 0.9 beta  
**Sist oppdatert:** 2. februar 2026
