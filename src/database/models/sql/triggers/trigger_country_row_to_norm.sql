CREATE OR REPLACE FUNCTION raw.fn_normalize_country()
RETURNS TRIGGER AS $$
BEGIN
    -- Синхронизируем регион
    INSERT INTO normalized.regions (id, iso2_code, name)
    VALUES (NEW.region_id, NEW.region_iso2_code, NEW.region_name)
    ON CONFLICT (id) DO UPDATE SET
        iso2_code = EXCLUDED.iso2_code,
        name = EXCLUDED.name;

    -- Синхронизируем уровень дохода
    INSERT INTO normalized.income_levels (id, iso2_code, name)
    VALUES (NEW.income_level_id, NEW.income_level_iso2_code, NEW.income_level_name)
    ON CONFLICT (id) DO UPDATE SET
        iso2_code = EXCLUDED.iso2_code,
        name = EXCLUDED.name;

    -- Синхронизируем страну
    INSERT INTO normalized.countries (
        id, iso2_code, name, capital_city,
        longitude, latitude, region_id, income_level_id
    )
    VALUES (
        NEW.id
        , NEW.iso2_code
        , NEW.name
        , NULLIF(NEW.capital_city, '')
        , NULLIF(NEW.longitude, '')::DOUBLE PRECISION
        , NULLIF(NEW.latitude, '')::DOUBLE PRECISION
        , NEW.region_id
        , NEW.income_level_id
    )
    ON CONFLICT (id) DO UPDATE SET
        iso2_code = EXCLUDED.iso2_code,
        name = EXCLUDED.name,
        capital_city = EXCLUDED.capital_city,
        longitude = EXCLUDED.longitude,
        latitude = EXCLUDED.latitude,
        region_id = EXCLUDED.region_id,
        income_level_id = EXCLUDED.income_level_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_after_upsert_raw_country ON raw.countries;

CREATE TRIGGER trg_after_upsert_raw_country
AFTER INSERT OR UPDATE ON raw.countries
FOR EACH ROW
EXECUTE FUNCTION raw.fn_normalize_country();