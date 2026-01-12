CREATE OR REPLACE FUNCTION raw.fn_normalize_indicator_data()
RETURNS TRIGGER AS $$
DECLARE
    v_numeric_val FLOAT;
BEGIN
    -- Попытка конвертации строки в число
    BEGIN
        v_numeric_val := NEW.value::FLOAT;
    EXCEPTION WHEN others THEN
        v_numeric_val := NULL;
    END;

    -- Синхронизация фактов
    INSERT INTO normalized.indicator_data (
        indicator_id,
        country_id,
        year,
        value_numeric,
        value_string,
        extra_info
    )
    VALUES (
        NEW.indicator_id,
        NEW.country_id,
        NEW.year,
        v_numeric_val,
        CASE WHEN v_numeric_val IS NULL THEN NEW.value ELSE NULL END,
        NEW.api_response  -- Переносим JSON ответ как доп. информацию
    )
    ON CONFLICT ON CONSTRAINT uq_norm_data
    DO UPDATE SET
        value_numeric = EXCLUDED.value_numeric,
        value_string = EXCLUDED.value_string,
        extra_info = EXCLUDED.extra_info,
        normalized_at = CURRENT_TIMESTAMP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_after_insert_raw_data
AFTER INSERT OR UPDATE ON raw.indicator_data
FOR EACH ROW
EXECUTE FUNCTION raw.fn_normalize_indicator_data();