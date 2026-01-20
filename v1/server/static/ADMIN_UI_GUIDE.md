# Admin Dashboard UI Guide

## 🎯 Overzicht

De MobyPark Admin Dashboard UI biedt een complete interface voor administrators om het systeem te beheren en monitoren.

## 🔐 Admin Login

### Hoe krijg je admin toegang?

1. **Registreer een admin account:**
   - Ga naar de Auth tab
   - Gebruik het registratieformulier
   - **Let op:** Stel het `role` veld in op `ADMIN` (dit moet je handmatig doen via API of database)

2. **Login met admin account:**
   - Vul je username en password in
   - De UI haalt automatisch je role op
   - Als je admin bent, verschijnt de **👑 Admin Dashboard** tab

### Bestaande admin accounts (in test database):
- Username: `admin_user` (als deze bestaat in je database)
- Je kunt een admin account maken door tijdens registratie de role te wijzigen

## 📊 Admin Dashboard Features

### 1. Dashboard Overview (📊)
Toont een compleet overzicht van het systeem:
- **Users**: Totaal aantal, admins, reguliere users, nieuwe users
- **Parking Lots**: Totaal, capaciteit, bezetting, bezettingspercentage
- **Sessions**: Totaal, actief, afgerond
- **Revenue**: Totale omzet, refunds, netto omzet, openstaande betalingen
- **Recent Activity**: Laatste sessies en betalingen

**Gebruik:**
- Klik op "📊 Dashboard Overview"
- Bekijk de statistieken in de gekleurde kaarten
- Open de details voor recente activiteit

### 2. All Users (👥)
Toont een tabel met alle gebruikers in het systeem:
- User ID, username, naam, email, role, creation date
- Kleurcodering voor roles (geel voor ADMIN, grijs voor USER)
- "Details" knop om specifieke gebruikersinformatie te bekijken

**Gebruik:**
- Klik op "👥 All Users"
- Scroll door de tabel
- Klik op "Details" bij een gebruiker om hun voertuigen, sessies en betalingen te zien

### 3. Parking Stats (🅿️)
Gedetailleerde statistieken per parking lot:
- Locatie, capaciteit, bezetting
- Bezettingspercentage (rood >80%, geel >50%, groen <50%)
- Totaal aantal sessies, actieve sessies
- Totale omzet per parking lot

**Gebruik:**
- Klik op "🅿️ Parking Stats"
- Bekijk elk parking lot in een apart blok
- Let op de kleurcodering voor bezettingspercentage

### 4. Active Sessions (🔴)
Alle momenteel actieve parkeer sessies:
- Gebruikersinformatie
- Voertuig details (kenteken, merk, model)
- Parking lot locatie
- Start tijd en huidige duur

**Gebruik:**
- Klik op "🔴 Active Sessions"
- Bekijk real-time actieve sessies
- Geen actieve sessies? Dan zie je een melding

### 5. Revenue Summary (💰)
Financieel overzicht:
- **Revenue by Parking Lot**: Omzet, refunds, aantal betalingen per parking lot
- **Top Paying Users**: Top 10 gebruikers met hoogste betalingen

**Gebruik:**
- Klik op "💰 Revenue Summary"
- Bekijk welke parking lots het meeste opbrengen
- Identificeer je meest waardevolle klanten

### 6. System Health (🏥)
Systeem gezondheid monitoring:
- Onbetaalde afgeronde sessies (probleem)
- Lange actieve sessies >7 dagen (mogelijk probleem)
- Openstaande betalingen (waarschuwing)
- Inactieve gebruikers >90 dagen (info)

**Status:**
- ✅ **Healthy**: Alles in orde
- ⚠️ **Needs Attention**: Er zijn issues die aandacht vereisen

**Gebruik:**
- Klik op "🏥 System Health"
- Controleer de overall status
- Lees de waarschuwingen en aanbevelingen
- Neem actie op basis van de voorgestelde stappen

## 🎨 Visuele Indicatoren

### Kleuren:
- **Groen**: Gezond, goed, positief
- **Geel/Oranje**: Waarschuwing, aandacht vereist
- **Rood**: Probleem, kritiek, urgent
- **Grijs**: Neutraal, informatief
- **Paars/Blauw**: Admin functionaliteit

### Icons:
- 👑 Admin indicator
- 📊 Statistieken
- 👥 Gebruikers
- 🅿️ Parking lots
- 🔴 Actief
- 💰 Financieel
- 🏥 Gezondheid
- ✅ Succesvol
- ⚠️ Waarschuwing
- ❌ Error

## 💡 Tips voor Admins

1. **Dagelijks:**
   - Check System Health voor urgent issues
   - Bekijk Active Sessions voor abnormale patronen

2. **Wekelijks:**
   - Review Revenue Summary
   - Check Parking Stats voor capaciteitsproblemen

3. **Maandelijks:**
   - Analyseer top users
   - Review inactieve gebruikers

4. **Bij problemen:**
   - Start met System Health
   - Gebruik User Details voor specifieke gebruikersproblemen
   - Check Active Sessions voor lopende issues

## 🔧 Technische Details

### API Endpoints gebruikt:
- `GET /admin/dashboard` - Dashboard overzicht
- `GET /admin/users` - Alle gebruikers
- `GET /admin/users/{id}` - Specifieke gebruiker
- `GET /admin/parking-lots/stats` - Parking statistieken
- `GET /admin/sessions/active` - Actieve sessies
- `GET /admin/revenue/summary` - Omzet samenvatting
- `GET /admin/system/health` - Systeem gezondheid

### Beveiliging:
- Alle admin endpoints vereisen een admin session token
- Reguliere users krijgen 403 Forbidden bij admin endpoints
- Admin tab is alleen zichtbaar voor ingelogde admins

### Browser Compatibiliteit:
- Modern browsers (Chrome, Firefox, Edge, Safari)
- JavaScript moet enabled zijn
- LocalStorage wordt gebruikt voor sessie management

## 🐛 Troubleshooting

### Admin tab verschijnt niet na login:
1. Controleer of je account role "ADMIN" is in de database
2. Log uit en log opnieuw in
3. Check de browser console voor errors

### 403 Forbidden errors:
- Je account heeft geen admin rechten
- Session token is verlopen, log opnieuw in

### Data laadt niet:
1. Check of de API server draait (http://localhost:8000)
2. Open browser console voor error details
3. Verifieer dat je nog steeds ingelogd bent

### Styling problemen:
- Hard refresh de browser (Ctrl+F5 / Cmd+Shift+R)
- Clear browser cache
- Check of CSS correct geladen is

## 📞 Support

Voor vragen of problemen:
- Check de API documentatie: http://localhost:8000/docs
- Zie de API guide: `ADMIN_DASHBOARD_README.md`
- Test de endpoints met Swagger UI: http://localhost:8000/docs
