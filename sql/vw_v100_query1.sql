create or replace view query_1 as
WITH base_query as (
SELECT
     city,
     local_time,
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

avg_query AS (
SELECT
     city,
     year,
     month,
     avg(co) AS co_avg,
     avg(so2) AS so_avg
FROM base_query
GROUP BY  1,2,3
)

SELECT
     city,
     year,
     month,
     co_avg,
     so_avg
FROM avg_query
GROUP BY  1,2,3,4,5
having co_avg >= approx_percentile(co_avg,0.9) and so_avg >= approx_percentile(so_avg,0.9)
order by 4 desc,5 desc
