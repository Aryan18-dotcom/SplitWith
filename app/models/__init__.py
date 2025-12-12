from flask import current_app

class GetDB:
    @staticmethod
    def _get_db():
        db_name = current_app.config.get('MONGO_DBNAME')
        if not db_name:
            raise RuntimeError("MONGO_DBNAME is not set in config.py.")

        try:
            db = current_app.mongo_client[db_name]
            db.client.admin.command('ping')
            return db
        
        except Exception as e:
            raise RuntimeError(f"MONGO ERROR: {e}")
