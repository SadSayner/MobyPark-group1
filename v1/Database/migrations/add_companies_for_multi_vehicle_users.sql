PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;


INSERT OR IGNORE INTO user_vehicles (user_id, vehicle_id)
SELECT DISTINCT user_id, vehicle_id
FROM reservations;

INSERT INTO companies (name, created_at)
SELECT user_id || '''s Company',
       CURRENT_TIMESTAMP
FROM user_vehicles
GROUP BY user_id
HAVING COUNT(vehicle_id) > 1;

UPDATE user_vehicles
SET company_id = (
    SELECT c.company_id
    FROM companies c
    WHERE c.name = user_vehicles.user_id || '''s Company'
)
WHERE user_id IN (
    SELECT user_id
    FROM user_vehicles
    GROUP BY user_id
    HAVING COUNT(vehicle_id) > 1
);

COMMIT;
-- Verification Query
SELECT uv.user_id,
       uv.vehicle_id,
       uv.company_id,
       c.name AS company_name
FROM user_vehicles uv
LEFT JOIN companies c ON uv.company_id = c.company_id
ORDER BY uv.user_id;
