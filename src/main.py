from src.pipline.manager import WBPiplineManager
from config import WBSettings, DatabaseConfig

def main():
    db_cfg = DatabaseConfig()
    wb_cfg = WBSettings([], [], [])

    collector = WBPiplineManager(wb_cfg, db_cfg)
    collector.set_connection()
    collector.drop_data_storage()
    collector.init_data_storage()
    collector.sync_countries()
    collector.sync_indicators()
    collector.close_connection()

if __name__ == "__main__":
    main()