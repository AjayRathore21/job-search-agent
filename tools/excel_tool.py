"""
Tool to save job data into Excel files, upload to Cloudinary,
and store the result record in MongoDB (excel_results collection).
"""

import pandas as pd
import os
from datetime import datetime, timezone
from langchain_core.tools import tool

from tools.cloudinary_tool import upload_excel_to_cloudinary


def _write_excel_result_to_db(user_id: str, cloudinary_url: str, public_id: str, query: str, job_count: int):
    """Persist an excel_results record to MongoDB after successful upload."""
    try:
        from utils.db import get_db
        db = get_db()
        db["excel_results"].insert_one({
            "user_id":        user_id,
            "cloudinary_url": cloudinary_url,
            "public_id":      public_id,
            "query":          query,
            "job_count":      job_count,
            "created_at":     datetime.now(timezone.utc),
        })
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Could not write excel_result to MongoDB: {e}")


@tool
def save_jobs_to_excel(
    jobs_data: list[dict],
    query: str = "",
    filename: str | None = None,
    user_id: str = "default_user"
) -> str:
    """
    Saves a list of job dictionaries to an Excel file, uploads it to Cloudinary,
    and records the result in MongoDB under the given user_id.

    Args:
        jobs_data: List of job dicts e.g. [{"title": "...", "url": "..."}]
        query:     The original search query (stored in MongoDB for reference).
        filename:  Optional custom filename. Auto-generated if not provided.
        user_id:   The user/session ID — used to organise files in Cloudinary and MongoDB.
    """
    if not jobs_data:
        return "Error: No job data provided to save."

    # Build filename
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"jobs_{timestamp}.xlsx"

    # Build DataFrame
    df = pd.DataFrame(jobs_data)

    if 'title' in df.columns:
        df.rename(columns={'title': 'name'}, inplace=True)

    if 'url' in df.columns:
        df['apply link'] = df['url']
        df.drop(columns=['url'], inplace=True)

    if 'referral_url' in df.columns:
        df['linkedin referral'] = df['referral_url']
        df.drop(columns=['referral_url'], inplace=True)


    # Save locally
    file_path = os.path.abspath(filename)
    try:
        df.to_excel(file_path, index=False, engine="openpyxl")
    except Exception as e:
        return f"Error saving Excel file locally: {str(e)}"

    # Upload to Cloudinary
    upload_result = upload_excel_to_cloudinary(file_path, user_id)

    if "error" in upload_result:
        return (
            f"✅ Saved {len(jobs_data)} jobs locally at: {file_path}\n"
            f"⚠️ Cloudinary upload failed: {upload_result['error']}\n"
            f"📝 MongoDB record NOT saved (no URL available)."
        )

    cloudinary_url = upload_result["url"]
    public_id      = upload_result["public_id"]

    # Write record to MongoDB
    _write_excel_result_to_db(
        user_id=user_id,
        cloudinary_url=cloudinary_url,
        public_id=public_id,
        query=query,
        job_count=len(jobs_data),
    )

    return (
        f"✅ Saved {len(jobs_data)} jobs to Excel.\n"
        f"☁️ Uploaded to Cloudinary for user '{user_id}'.\n"
        f"📦 Record saved to MongoDB (excel_results).\n"
        f"🔗 Download link: {cloudinary_url}"
    )
