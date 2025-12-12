# Assuming this file is where your GetDB class resides

from .. import mongo
from flask import current_app
# Import specific PyMongo exceptions for clearer debugging
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure, ConnectionFailure

class GetDB:
    @staticmethod
    def _get_db():
        db_name = current_app.config.get('MONGO_DBNAME')
        
        if not db_name:
            raise RuntimeError("MONGO_DBNAME is not set in config.py.")
        
        try:
            db = mongo.cx[db_name]
            db.client.admin.command('ping') 
            
            print("MONGO SUCCESS: Database connection verified.")
            return db

        except ServerSelectionTimeoutError as e:
            error_message = f"MONGO ERROR: Server Timeout. Check Atlas IP Whitelist and Network. Details: {e}"
            print(error_message)
            raise RuntimeError(error_message)

        except OperationFailure as e:
            error_message = f"MONGO ERROR: Operation Failure. Check MONGO_URI credentials. Details: {e}"
            print(error_message)
            raise RuntimeError(error_message)

        except Exception as e:
            error_message = f"MONGO ERROR: An unexpected connection error occurred. Details: {e}"
            print(error_message)
            raise RuntimeError(error_message)