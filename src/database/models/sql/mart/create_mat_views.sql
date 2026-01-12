DROP MATERIALIZED VIEW IF EXISTS mart.indicator_data;

CREATE MATERIALIZED VIEW mart.indicator_data AS
WITH template AS (
  SELECT m.country_id
    , c.name AS country_name
    , m.indicator_id
    , i.name AS indicator_name
    , m.value_numeric AS value
    , c.region_id AS region_id
    , r.name AS region_name
    , c.income_level_id
    , il.name AS income_level_name
    , m.year AS year
    , MAKE_DATE(year, 1, 1) AS year_dt
    , (year / 10) * 10 AS decade

  FROM normalized.indicator_data AS m
  LEFT JOIN normalized.countries AS c ON c.id = m.country_id
  LEFT JOIN normalized.indicators AS i ON i.id = m.indicator_id
  LEFT JOIN normalized.income_levels AS il ON c.income_level_id = il.id
  LEFT JOIN normalized.regions AS r ON c.region_id = r.id
),
interpolation_preparation AS (
  -- В Posrgesql нет возможности использовать IGNORE NULLS чтобы пропускать строки null
  -- При этм четко нужно определять начало интервала и конец для интерполяции, которые не null
  SELECT *
    , LAST_VALUE(CASE WHEN value IS NOT NULL THEN value END) OVER search_prev_notnull AS prev_value
    , LAST_VALUE(CASE WHEN value IS NOT NULL THEN year END) OVER search_prev_notnull AS prev_year
    , FIRST_VALUE(CASE WHEN value IS NOT NULL THEN value END) OVER search_next_notnull AS next_value
    , FIRST_VALUE(CASE WHEN value IS NOT NULL THEN year END) OVER search_next_notnull AS next_year
  FROM template
  WINDOW search_prev_notnull AS (
    PARTITION BY country_id, indicator_id
    ORDER BY year
    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
  ),
  search_next_notnull AS (
    PARTITION BY country_id, indicator_id
    ORDER BY year
    ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING
  )
),
template_interpolation AS (
  SELECT *
    , CASE
      WHEN value IS NOT NULL THEN value
      WHEN prev_value IS NOT NULL AND next_value IS NOT NULL AND next_year > prev_year
      THEN prev_value + (next_value - prev_value) * (year - prev_year) / (next_year - prev_year)
      ELSE NULL
    END AS value_filled
  FROM interpolation_preparation
),
calculation AS (
  -- Дополнительные параметры
  -- Изменение показателя (абсолютное и относительное) и волатильность на плече в пять лет
  SELECT *
    , value_filled - LAG(value_filled) OVER search_next AS del_val
    , (value_filled - LAG(value_filled) OVER search_next) / NULLIF(LAG(value_filled) OVER search_next, 0) AS prcnt_del
    , STDDEV(value) OVER (
      PARTITION BY country_id, indicator_id
      ORDER BY year
      ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
      ) AS vol_5
  FROM template_interpolation
  WINDOW search_next AS (
    PARTITION BY country_id, indicator_id
    ORDER BY year
  )
)
SELECT *
FROM calculation;

CREATE UNIQUE INDEX uq_mart_indicator_data ON mart.indicator_data (country_id, indicator_id, year);
CREATE INDEX idx_mart_indicator_region ON mart.indicator_data (region_id);
CREATE INDEX idx_mart_indicator_income ON mart.indicator_data (income_level_id);