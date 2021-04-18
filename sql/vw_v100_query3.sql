create or replace view query_3 as

with base_query as (
SELECT
   city,
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
 
high_hourly_avg as (
select
   city,
   year,
   month,
   day,
   pm25_avg
from (
select
   city,
   year,
   month,
   day,
   avg(pm25) as pm25_avg,
   rank() over (partition by year, month, day, extract(hour from date) order by avg(pm25) desc) as rank
from base_query
group by 1,2,3,4, extract(hour from date)
order by 5 desc
)
where rank <= 10
)

select
   b.city,
   b.year,
   b.month,
   b.day,
   avg(b.so2)                   AS mean_so2,
   avg(b.co)                    AS mean_co,
   count(distinct b.co)         AS mode_co,
   count(distinct b.so2)        AS mode_so2,
   approx_percentile(b.so2,0.5) AS median_so2,
   approx_percentile(b.co,0.5)  AS median_co
from base_query b
inner join high_hourly_avg h on h.city = b.city and h.year=b.year and  h.month= b.month and  h.day=b.day
group by 1,2,3,4
