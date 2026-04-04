"""
Cloudinary integration for uploading job search Excel result files.
Files are stored under a folder named after the userId for easy organization.
"""

import os
import cloudinary
import cloudinary.uploader
from datetime import datetime


def init_cloudinary():
    """Initialize Cloudinary config from environment variables."""
    cloudinary.config(
        cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
        api_key=os.environ.get("CLOUDINARY_API_KEY"),
        api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
        secure=True
    )


def upload_excel_to_cloudinary(file_path: str, user_id: str) -> dict:
    """
    Uploads an Excel file to Cloudinary under a folder named after the user_id.

    Args:
        file_path: Absolute local path to the .xlsx file.
        user_id:   The user/session identifier (used as the Cloudinary folder name).

    Returns:
        A dict with:
            - 'url'        : The secure download URL of the uploaded file.
            - 'public_id'  : The Cloudinary public ID.
            - 'user_id'    : The user_id the file was stored under.
        Or on failure:
            - 'error'      : Error message string.
    """
    try:
        init_cloudinary()

        # Build a timestamped filename so each upload is unique
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        public_id = f"job_results/{user_id}/{base_name}_{timestamp}"

        result = cloudinary.uploader.upload(
            file_path,
            public_id=public_id,
            resource_type="raw",        # Required for non-image files like .xlsx
            overwrite=False,
            use_filename=False,
        )

        return {
            "url": result.get("secure_url"),
            "public_id": result.get("public_id"),
            "user_id": user_id,
        }

    except Exception as e:
        return {"error": f"Cloudinary upload failed: {str(e)}"}


def delete_excel_from_cloudinary(public_id: str) -> bool:
    """
    Deletes an Excel file from Cloudinary by its public ID.

    Args:
        public_id:   The Cloudinary public ID (e.g. 'job_results/user1/filename_timestamp').

    Returns:
        True if the file was deleted successfully, False otherwise.
    """
    try:
        init_cloudinary()

        # Excel files are uploaded with resource_type='raw'
        result = cloudinary.uploader.destroy(
            public_id,
            resource_type="raw"
        )

        # Check the response status
        if result.get("result") == "ok":
            return True
        else:
            print(f"❌ Cloudinary deletion failed: {result}")
            return False

    except Exception as e:
        print(f"❌ Cloudinary deletion error: {e}")
        return False

