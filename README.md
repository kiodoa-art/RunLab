# RunLab 0.1 – Home Assistant App (første fungerende prototype)

RunLab er en privat PWA med Python-server og SQLite. Importerer FIT, TCX, GPX og et fleksibelt JSON-format.

## Test lokalt (uden Home Assistant)

```bash
cd runlab/rootfs/app
python3 server.py
```
Åbn http://localhost:8099. FIT-import kræver `pip install fitparse`.

## Home Assistant OS

Dette er en **kildekodepakke**, ikke en allerede installeret app. For at installere som Home Assistant App:

1. Læg hele repository-indholdet i et GitHub-repository, og erstat placeholder-URL i `repository.yaml` og `runlab/config.yaml` med den rigtige URL.
2. Home Assistant → Indstillinger → Apps → App-butik → menu → Repositories → tilføj GitHub-repository-URL.
3. Find RunLab, installér og start.
4. Åbn `http://DIN-HA-IP:8099` fra dit hjemmenetværk.

**Vigtigt:** Port 8099 er uden login i denne prototype. Den må kun eksponeres på et betroet lokalt netværk. Opret IKKE port-forwarding eller offentlig proxy. PWA-installation på telefon kræver normalt HTTPS (eller localhost); det sættes op i en senere version.

## Datamodel

`/data/runlab.sqlite3` er vedvarende lagring. Eksportér JSON-backup fra knappen i brugerfladen. Der er endnu ikke automatiseret backup eller backup-import.

## Kendte begrænsninger

- FIT/TCX/GPX og JSON håndteres, men Garmin-varianter og eksisterende løbebåndseksport skal valideres med rigtige filer.
- GPX har ofte ikke distance, puls eller varighed. Ingen opdigtede data tilføjes.
- FIT/TCX-data har varierende feltindhold, og eksport kan indeholde andet end løb.
- Diagrammer viser basale træningsdata; avanceret konditionsanalyse, målredigering, automatisk synkronisering, Google Drive-backup, login og sikker ekstern adgang er **ikke** implementeret endnu.
- Fil-dubletter identificeres ved SHA-256 af filindhold, ikke ved logisk aktivitets-ID.
- PWA har ingen app-ikoner endnu.
- Standardinstallationen åbner port 8099 på HA-værten; begræns adgang på netværksniveau.

## JSON-eksempel

```json
{"started":"2026-10-11T08:00:00+02:00","duration_s":1800,"distance_km":3.2,"points":[{"time":"2026-10-11T08:00:00+02:00","hr":130,"speed_kmh":6.4}]}
```
