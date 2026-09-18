from flask import Flask, request, jsonify, Response
from pymongo import MongoClient
from gridfs import GridFS
from bson import ObjectId
from dotenv import load_dotenv
import os
import uuid
from datetime import datetime


# =========================================================
# Load configuration
# =========================================================

load_dotenv()


# =========================================================
# Configuration
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "my_db")

PUBLIC_URL = os.getenv(
    "PUBLIC_URL",
    "http://localhost:3000"
).rstrip("/")

PORT = int(os.getenv("PORT", "10000"))

# Maximum upload size = 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024


if not MONGO_URI:
    raise Exception("MONGO_URI is missing from .env")


# =========================================================
# MongoDB Cloud
# =========================================================

client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=10000
)

try:
    client.admin.command("ping")
    print("MongoDB Cloud connected successfully")

except Exception as e:
    print("MongoDB connection FAILED:")
    print(e)
    raise


db = client[MONGO_DATABASE]

# GridFS bucket
fs = GridFS(db, collection="images")

print(f"MongoDB Database: {MONGO_DATABASE}")
print("GridFS ready")


# =========================================================
# Flask
# =========================================================

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE


# =========================================================
# Allowed image types
# =========================================================

ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp"
}


# =========================================================
# Home / Health Check
# =========================================================

@app.route("/", methods=["GET"])
def home():

    return """
    <html>
    <head>
        <title>Image Server</title>

        <meta name="viewport"
              content="width=device-width, initial-scale=1">
    </head>

    <body style="font-family:Arial; padding:30px;">

        <h2>Image Server is Running ✅</h2>

        <p>MongoDB GridFS is connected.</p>

    </body>
    </html>
    """


# =========================================================
# Upload Image
# =========================================================

@app.route("/upload-image", methods=["POST"])
def upload_image():

    try:

        # -------------------------------------------------
        # Check image exists
        # -------------------------------------------------

        if "image" not in request.files:

            return jsonify({
                "success": False,
                "message": "No image received."
            }), 400


        file = request.files["image"]


        # -------------------------------------------------
        # Check filename
        # -------------------------------------------------

        if file.filename == "":

            return jsonify({
                "success": False,
                "message": "No file selected."
            }), 400


        # -------------------------------------------------
        # Check MIME type
        # -------------------------------------------------

        content_type = file.content_type

        if content_type not in ALLOWED_TYPES:

            return jsonify({
                "success": False,
                "message":
                    "Only JPG, PNG, GIF and WEBP images are allowed."
            }), 400


        # -------------------------------------------------
        # Generate unique filename
        # -------------------------------------------------

        extension = os.path.splitext(
            file.filename
        )[1].lower()


        filename = (
            str(uuid.uuid4()) +
            extension
        )


        # -------------------------------------------------
        # Metadata
        # -------------------------------------------------

        metadata = {

            "original_name": file.filename,

            "content_type": content_type,

            "uploaded_at": datetime.utcnow()
        }


        # -------------------------------------------------
        # Read image
        # -------------------------------------------------

        image_data = file.read()


        # -------------------------------------------------
        # Check file size
        # -------------------------------------------------

        if len(image_data) > MAX_FILE_SIZE:

            return jsonify({
                "success": False,
                "message":
                    "Maximum image size is 10 MB."
            }), 400


        # -------------------------------------------------
        # Save image to MongoDB GridFS
        # -------------------------------------------------

        file_id = fs.put(

            image_data,

            filename=filename,

            content_type=content_type,

            metadata=metadata
        )


        # -------------------------------------------------
        # Create image URL
        # -------------------------------------------------

        image_url = (
            f"{PUBLIC_URL}/image/{str(file_id)}"
        )


        print("")
        print("Image uploaded successfully")
        print(f"File ID: {file_id}")
        print(f"Image URL: {image_url}")


        # -------------------------------------------------
        # Response
        # -------------------------------------------------

        return jsonify({

            "success": True,

            "message":
                "Image uploaded successfully.",

            "file_id":
                str(file_id),

            "url":
                image_url
        })


    except Exception as e:

        print("Upload error:", e)

        return jsonify({

            "success": False,

            "message":
                "Image upload failed.",

            "error":
                str(e)
        }), 500


# =========================================================
# View Image
# =========================================================

@app.route("/image/<file_id>", methods=["GET"])
def view_image(file_id):

    try:

        # -------------------------------------------------
        # Validate ObjectId
        # -------------------------------------------------

        try:

            object_id = ObjectId(file_id)

        except Exception:

            return "Invalid image ID.", 400


        # -------------------------------------------------
        # Find GridFS file
        # -------------------------------------------------

        grid_file = fs.find_one({
            "_id": object_id
        })


        if grid_file is None:

            return "Image not found.", 404


        # -------------------------------------------------
        # Read image
        # -------------------------------------------------

        image_data = grid_file.read()


        # -------------------------------------------------
        # MIME type
        # -------------------------------------------------

        content_type = (
            grid_file.content_type
            or "image/jpeg"
        )


        # -------------------------------------------------
        # Return image
        # -------------------------------------------------

        return Response(

            image_data,

            mimetype=content_type,

            headers={

                "Content-Disposition":
                    "inline",

                "Cache-Control":
                    "public, max-age=3600"
            }
        )


    except Exception as e:

        print("View error:", e)

        return "Server error.", 500


# =========================================================
# Delete Image
# =========================================================

@app.route("/image/<file_id>", methods=["DELETE"])
def delete_image(file_id):

    try:

        object_id = ObjectId(file_id)

        fs.delete(object_id)


        return jsonify({

            "success": True,

            "message":
                "Image deleted successfully."
        })


    except Exception as e:

        print("Delete error:", e)


        return jsonify({

            "success": False,

            "message":
                "Image not found."
        }), 404


# =========================================================
# File Too Large
# =========================================================

@app.errorhandler(413)
def file_too_large(error):

    return jsonify({

        "success": False,

        "message":
            "Image is too large. Maximum size is 10 MB."
    }), 413


# =========================================================
# Start Server
# =========================================================

if __name__ == "__main__":

    print("")
    print("======================================")
    print("Python Image Server")
    print("======================================")

    print(f"Local URL: http://localhost:{PORT}")

    print("")

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )