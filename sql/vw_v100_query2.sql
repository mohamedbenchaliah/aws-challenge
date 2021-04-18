create or replace view query_2 as
WITH base_query as (
SELECT
     city,
     local_time,
     year,
     month,
     day,
     max(if(parameter='co', if(unit='µg/m³', value*0.000873, value), 0))        AS co,
     max(if(parameter='so2', if(unit='µg/m³', value*0.000382, value), 0))       AS so2,
     max(if(parameter='pm25', value, 0)) AS pm25
FROM ${GlueTableName}
GROUP BY  1,2,3,4,5
ORDER BY  max(if(parameter='pm25', value, 0)) DESC
),

top5_cities as (
select
     city,
     year,
     month,
     day,
     avg(pm25) as pm25_avg,
     rank() over (partition by year, month, day order by avg(pm25) desc) as rank
from base_query
group by 1,2,3,4
order by 5 desc
)

select
     city,
     year,
     month,
     day,
     pm25_avg
from top5_cities where rank <= 5
order by day
