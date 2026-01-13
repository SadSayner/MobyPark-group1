-- Toon gebruikers met meerdere voertuigen
SELECT user_id, COUNT(*) AS vehicle_count
FROM user_vehicles
GROUP BY user_id
HAVING COUNT(*) > 1;

INSERT INTO companies (name, created_at)
SELECT 'Bedrijf van gebruiker ' || uv.user_id,
       CURRENT_TIMESTAMP
FROM user_vehicles uv
GROUP BY uv.user_id
HAVING COUNT(uv.vehicle_id) > 1;


UPDATE user_vehicles
SET company_id = (
    SELECT c.company_id
    FROM companies c
    WHERE c.name = 'Bedrijf van gebruiker ' || user_vehicles.user_id
)
WHERE user_id IN (
    SELECT user_id
    FROM user_vehicles
    GROUP BY user_id
    HAVING COUNT(vehicle_id) > 1
);


SELECT uv.user_id, uv.vehicle_id, uv.company_id, c.name
FROM user_vehicles uv
JOIN companies c ON uv.company_id = c.company_id
ORDER BY uv.user_id;
