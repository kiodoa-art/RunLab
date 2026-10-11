# RunLab 0.3 – Home Assistant og lokal LAN-adgang

RunLab samler løbebånds- og Garmin-træning (JSON, FIT, TCX og GPX) i en lokal SQLite-database på Home Assistant. Ingen cloud-upload.

## Opdatering fra 0.2

1. Opdater appen til **0.3.0** via Home Assistant → Indstillinger → Apps → RunLab.
2. Åbn **Konfiguration** og angiv **runlab_password** på mindst 12 tegn. Vælg en unik adgangskode; den gemmes i Home Assistants appindstillinger, ikke i GitHub.
3. Start appen igen. Både Ingress og direkte adgang kræver nu HTTP Basic-login med brugernavn **runlab** og den valgte adgangskode.
4. **Valgfrit – kun på et betroet hjemmenetværk:** Under appens **Netværk** kan du tildele containerport **8099/tcp** til værtsport **8099**. Standard er **ikke eksponeret**. Besøg derefter `http://192.168.50.216:8099/` på dit lokale netværk. Kontrollér at din router **ikke** videresender porten, og at du ikke offentliggør den via proxy.
5. Behold Ingress som sikker standardadgang. Hvis du vil have et selvstændigt appvindue på Windows, kan Chrome-menuen **Gem og del → Opret genvej → Åbn som vindue** bruges, hvor tilgængeligt.

**Vigtig begrænsning:** HTTP på et LAN er **ikke krypteret**, selv med Basic-login. Adgangskoden kan opsnappes på et kompromitteret netværk. Brug ikke denne direkte HTTP-adgang på gæstenet, offentligt Wi-Fi eller internet. En fuldt installerbar PWA med service worker på telefon og almindelig LAN-IP kræver HTTPS med et betroet certifikat. Version 0.3 leverer derfor selvstændig lokal webadgang og appvindue på understøttede computere, men ikke garanteret PWA-installation på mobil. Eksponér ikke port 8099 før du har vurderet dette.

## Drift og datalagring

- Data lagres under `/data/runlab.sqlite3` og bevares ved almindelig app-opdatering.
- RunLab har ikke adgang til Home Assistants `/config`.
- Upload er begrænset til 25 MB og højst 50.000 målepunkter pr. fil.
- Garmin- og løbebåndsformater skal stadig afprøves med rigtige eksportfiler.
- Brug **Eksportér data** til en manuel JSON-sikkerhedskopi.
- Ved første opstart efter opdatering **skal adgangskoden angives**, ellers stopper RunLab bevidst med en forklaring i loggen.

## Udvikling lokalt

```bash
cd runlab/rootfs/app
RUNLAB_PASSWORD='vælg-en-lang-testkode' python3 server.py
```

Åbn `http://localhost:8099` og log ind med brugernavnet `runlab`.
