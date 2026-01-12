CREATE OR REPLACE VIEW mart.v_global_ag AS
SELECT
    indicator_id
    , indicator_name
    , year
    , year_dt
    , AVG(value_filled) AS mean_value
    , STDDEV(value_filled) AS std_value
    , MIN(value_filled) AS min_value
    , MAX(value_filled) AS max_value
FROM mart.indicator_data
GROUP BY indicator_id, indicator_name, year, year_dt;

CREATE OR REPLACE VIEW mart.v_region_ag AS
SELECT
    region_id
    , region_name
    , indicator_id
    , indicator_name
    , year
    , year_dt
    , AVG(value_filled) AS mean_value
    , STDDEV(value_filled) AS std_value
FROM mart.indicator_data
GROUP BY region_id, region_name, indicator_id, indicator_name, year, year_dt;

CREATE OR REPLACE VIEW mart.v_income_level_ag AS
SELECT
    income_level_id
    , income_level_name
    , indicator_id
    , indicator_name
    , year
    , year_dt
    , AVG(value_filled) AS mean_value
    , STDDEV(value_filled) AS std_value
FROM mart.indicator_data
GROUP BY income_level_id, income_level_name, indicator_id, indicator_name, year, year_dt;

CREATE OR REPLACE VIEW mart.v_country_rank AS
SELECT country_id
    , country_name
    , indicator_id
    , indicator_name
    , year
    , value_filled
    , RANK() OVER (
        PARTITION BY indicator_id, year
        ORDER BY value_filled DESC
    ) AS rank_desc
    , RANK() OVER (
        PARTITION BY indicator_id, year
        ORDER BY value_filled ASC
    ) AS rank_asc
    , COUNT(*) OVER (
    PARTITION BY indicator_id, year
  ) AS countries_in_year
FROM mart.indicator_data
WHERE value IS NOT NULL;