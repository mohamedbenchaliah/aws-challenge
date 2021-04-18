create or replace view query_4 as
WITH base_query as (
SELECT
     english_short_name as country,
     from_iso8601_timestamp(local_time) as date,
     year,
     month,
     day,
     max(if(parameter='co', if(unit='µg/m³', value*0.000873, value), 0)) AS co,
     max(if(parameter='so2', if(unit='µg/m³', value*0.000382, value), 0)) AS so2,
     max(if(parameter='pm25', value, 0)) AS pm25
FROM ${GlueTableName}
GROUP BY  1,2,3,4,5
ORDER BY  max(if(parameter='pm25', value, 0)) DESC
),

IndexGrid AS (
select
    1 as level,
    15 as pm25,
    4 as co,
    0.02 as so2
union
select
    2 as level,
    30 as pm25,
    6 as co,
    0.06 as so2
union
select
    3 as level,
    55 as pm25,
    8 as co,
    0.12 as so2
),

IndexStatus AS (
SELECT
    1 AS level,
    'LOW' AS status
UNION
SELECT
    2 AS level,
    'MEDIUM' AS status
UNION
SELECT
    3 AS level,
    'HIGH' AS status
)

SELECT
    country,
    extract(hour from date) as hour,
    year,
    month,
    day,
    qr.co,
    qr.so2,
    qr.pm25,
    status,
    MAX(index.level) as index
FROM IndexGrid index
JOIN base_query qr on 1=1
JOIN IndexStatus qi on index.level = qi.level
WHERE index.pm25 < qr.pm25 OR index.co < qr.co OR index.so2 < qr.so2
group by 1,2,3,4,5,6,7,8,9
order by index desc


--todo : fix US Diplomatic Post: Pristina	join code