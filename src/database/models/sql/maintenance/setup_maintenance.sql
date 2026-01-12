DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS pg_cron;
    RAISE NOTICE 'Extension pg_cron is ready.';
EXCEPTION WHEN insufficient_privilege THEN
    RAISE WARNING 'У пользователя недостаточно прав для создания расширения pg_cron. Пропустите этот шаг, если расширение не установлено администратором.';
WHEN OTHERS THEN
    RAISE WARNING 'Ошибка при попытке создать pg_cron: %', SQLERRM;
END $$;


CREATE OR REPLACE PROCEDURE raw.maintenance_cleanup()
LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM raw.indicators WHERE downloaded_at < NOW() - INTERVAL '7 days';
    COMMIT;
    DELETE FROM raw.countries WHERE downloaded_at < NOW() - INTERVAL '7 days';
    COMMIT;
    DELETE FROM raw.indicator_data WHERE downloaded_at < NOW() - INTERVAL '7 days';
    COMMIT;
END $$;

CREATE OR REPLACE PROCEDURE mart.refresh_analytics()
LANGUAGE plpgsql AS $$
BEGIN

    REFRESH MATERIALIZED VIEW CONCURRENTLY mart.world_bank_summary;
    COMMIT;
END $$;

-- Регистрируем задачи в кроне (если он доступен)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
        -- Чистим старые задачи, чтобы не было дублей
        PERFORM cron.unschedule(jobname) FROM cron.job WHERE jobname IN ('nightly-cleanup', 'nightly-refresh');

        -- Устанавливаем новое расписание
        PERFORM cron.schedule('nightly-cleanup', '0 2 * * *', 'CALL raw.maintenance_cleanup()');
        PERFORM cron.schedule('nightly-refresh', '0 3 * * *', 'CALL mart.refresh_analytics()');

        RAISE NOTICE 'Задачи pg_cron успешно запланированы.';
    END IF;
END $$;