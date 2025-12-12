import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = "static/uploads/groups"

def save_group_photo(file):
    if not file or file.filename == "":
        return None

    filename = secure_filename(file.filename)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)
    return filename

