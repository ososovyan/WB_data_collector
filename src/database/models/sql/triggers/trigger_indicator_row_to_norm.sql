CREATE OR REPLACE FUNCTION raw.fn_normalize_indicator()
RETURNS TRIGGER AS $$
BEGIN
    -- Синхронизируем источник
    INSERT INTO normalized.sources (id, name)
    VALUES (NEW.source_id, LEFT(NEW.source_name, 100))
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name;

    -- Синхронизируем индикатор
    INSERT INTO normalized.indicators (
        id,
        name,
        unit,
        source_note,
        source_organisation,
        source_id
    )
    VALUES (
        NEW.id
        , LEFT(NEW.name, 100)
        , LEFT(NEW.unit, 100)
        , LEFT(NEW.source_note, 200)
        , LEFT(NEW.source_organisation, 100)
        , NEW.source_id
    )
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        unit = EXCLUDED.unit,
        source_note = EXCLUDED.source_note,
        source_organisation = EXCLUDED.source_organisation,
        source_id = EXCLUDED.source_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


DROP TRIGGER IF EXISTS trg_after_upsert_raw_indicator ON raw.indicators;

CREATE TRIGGER trg_after_upsert_raw_indicator
AFTER INSERT OR UPDATE ON raw.indicators
FOR EACH ROW
EXECUTE FUNCTION raw.fn_normalize_indicator();