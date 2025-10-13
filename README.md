# Silent Devils MC Pusher Bot

En Discord bot til at koordinere pusher-jobs mellem medlemmer og pusherne i banden.

## Funktioner

### For Medlemmer
- Opret opgaver gennem en simpel formular
- Automatisk match med tilgængelige pusherne
- Privat kanal til kommunikation med pusheren

### For Pusherne
- Se alle tilgængelige jobs i oversigt
- Permanente opgaver altid tilgængelige
- "Tag Job" knap for at tage en opgave
- Automatisk privat kanal med medlemmet

## 🚀 Quick Deploy (5 minutter)

Se `QUICK_START.md` for hurtig deployment til Koyeb.

## 💻 Lokal Setup

1. Installer dependencies:
```bash
pip install -r requirements.txt
```

2. Opsæt miljøvariabler i `.env`:
```
DISCORD_TOKEN=din_bot_token_her
```

3. Kør botten:
```bash
python pusher_bot.py
```

## ☁️ Cloud Deployment

Botten er klar til deployment på:
- **Koyeb** (anbefalet - gratis)
- Heroku
- Railway
- Render

Se `DEPLOYMENT.md` for detaljeret guide.

## Kanal Konfiguration

Botten er konfigureret til følgende Discord IDs:
- **Medlem roller**: 1427380362933309553, 1427380405820199095, 1427380453257511072, 1427380496106524672, 1427380535834972301, 1427380589555876051, 1427380624813064304, 1427380609403191386
- **Admin roller**: 1427380609403191386, 1427380624813064304, 1427380589555876051, 1427380535834972301, 1427380496106524672, 1427380453257511072
- **Pusher rolle**: 1427387819264835715
- **Pusher opgave kanal**: 1427388722709663895
- **Pusher stats kanal**: 1427388707807297556
- **Medlem kanal**: 1419003264690556999
- **Ticket kategori**: 1427389435720241183
- **Absolut admin ID**: 356831538916098048

## Hvordan det fungerer

1. **Medlemmer** går til medlem-kanalen og trykker "Opret Opgave"
2. De udfylder en formular med titel, beskrivelse og belønning
3. Opgaven vises i pusher-kanalen sammen med permanente opgaver
4. **Pusherne** kan se alle opgaver og trykke "Tag Job" 
5. Der oprettes automatisk en privat kanal mellem medlem og pusher
6. De kan nu koordinere deres samarbejde privat

## Admin Funktioner

Administratorer med admin roller eller absolut admin ID kan administrere permanente opgaver:

### Kommandoer:
- `!pusherbot` - Vis admin hjælp
- `!pusherbot permopg add` - Tilføj ny permanent opgave
- `!pusherbot permopg edit` - Rediger eksisterende opgave  
- `!pusherbot permopg remove` - Fjern permanent opgave
- `!admin_reset` - Nulstil alle jobs (kun admin)

### Admin Workflow:
1. **Add**: Tryk på knap → udfyld modal → opgave tilføjes
2. **Edit**: Vælg opgave fra dropdown → rediger i modal
3. **Remove**: Vælg opgave fra dropdown → fjernes øjeblikkeligt

## Standard Permanente Opgaver

Botten starter med følgende permanente opgaver:
- 🚗 Køre rundt og sælge stoffer
- 💰 Hjælpe med money wash
- 🏠 Hjælpe med hus raids
- ⚔️ Hjælpe med gang wars
- 📦 Hjælpe med leveringer
- 🔫 Hjælpe med våben handel
- 🎯 Hjælpe med contracts

*Disse kan tilpasses via admin kommandoerne*
