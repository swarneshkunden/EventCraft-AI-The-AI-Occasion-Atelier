-- 1. Compare each event's total budget with recorded category spending.
SELECT
    e.id AS event_id,
    e.name AS event_name,
    e.total_budget,
    COALESCE(SUM(bc.spent), 0) AS total_spent,
    e.total_budget - COALESCE(SUM(bc.spent), 0) AS remaining_budget
FROM events AS e
LEFT JOIN budget_categories AS bc ON bc.event_id = e.id
GROUP BY e.id, e.name, e.total_budget
ORDER BY e.created_at DESC;

-- 2. Find task dependencies that are missing or not yet completed.
SELECT
    e.name AS event_name,
    t.title AS task,
    dependency.title AS unfinished_dependency,
    prerequisite.status AS dependency_status
FROM tasks AS t
JOIN events AS e ON e.id = t.event_id
CROSS JOIN LATERAL jsonb_array_elements_text(t.depends_on) AS dependency(title)
LEFT JOIN tasks AS prerequisite
    ON prerequisite.event_id = t.event_id
    AND prerequisite.title = dependency.title
WHERE t.status <> 'completed'
  AND (prerequisite.id IS NULL OR prerequisite.status <> 'completed')
ORDER BY e.name, t.title;

-- 3. Rank vendors with known quotes within each event and vendor category.
SELECT
    e.name AS event_name,
    v.vendor_type,
    v.name AS vendor_name,
    v.quoted_price,
    RANK() OVER (
        PARTITION BY v.event_id, v.vendor_type
        ORDER BY v.quoted_price
    ) AS price_rank
FROM vendors AS v
JOIN events AS e ON e.id = v.event_id
WHERE v.quoted_price IS NOT NULL
ORDER BY e.name, v.vendor_type, price_rank;

-- 4. Count guest records for each event, including events with no guests.
SELECT
    e.id AS event_id,
    e.name AS event_name,
    COUNT(g.id) AS guest_records
FROM events AS e
LEFT JOIN guests AS g ON g.event_id = e.id
GROUP BY e.id, e.name
ORDER BY e.name;

-- 5. List unfinished tasks whose ISO-formatted due date has passed.
SELECT
    e.name AS event_name,
    t.title AS task,
    t.status,
    t.due_date
FROM tasks AS t
JOIN events AS e ON e.id = t.event_id
WHERE t.due_date IS NOT NULL
  AND t.due_date < TO_CHAR(CURRENT_DATE, 'YYYY-MM-DD')
  AND t.status <> 'completed'
ORDER BY t.due_date, e.name;
