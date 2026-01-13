# MobyPark-group1

### Migratie: bedrijven aanmaken voor gebruikers met meerdere voertuigen

Dit script maakt automatisch bedrijven aan voor gebruikers met meerdere
voertuigen en koppelt hun voertuigen als bedrijfsauto’s.

Uitvoeren met:

sqlite3 v1/Database/MobyPark.db < v1/Database/migrations/add_companies_for_multi_vehicle_users.sql

### Migratie uitvoeren zonder sqlite3 CLI

Wanneer sqlite3 niet beschikbaar is in de console kan de migratie worden uitgevoerd met:

python v1/Database/run_migration.py
