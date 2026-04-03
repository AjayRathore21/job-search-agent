"""
Tool to save job data into Excel files and upload them to Cloudinary.
"""

import pandas as pd
import os
from datetime import datetime
from langchain_core.tools import tool

from tools.cloudinary_tool import upload_excel_to_cloudinary


@tool
def save_jobs_to_excel(jobs_data: list[dict], filename: str | None = None, user_id: str = "default_user") -> str:
    """
    Saves a list of job dictionaries (title and url) to an Excel file,
    then uploads the file to Cloudinary under the given user_id folder.
    Returns a summary with the Cloudinary download URL.

    Args:
        jobs_data: A list of dictionaries like [{"title": "...", "url": "..."}]
        filename:  Optional custom filename. Defaults to jobs_YYYYMMDD_HHMMSS.xlsx
        user_id:   The user/session ID — used to organize files in Cloudinary.
    """
    if not jobs_data:
        return "Error: No data provided."

    # Build filename
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"jobs_{timestamp}.xlsx"

    # Convert to DataFrame
    df = pd.DataFrame(jobs_data)

    if 'title' in df.columns:
        df.rename(columns={'title': 'name'}, inplace=True)

    if 'url' in df.columns:
        df['apply link'] = df['url'].apply(lambda x: f'=HYPERLINK("{x}", "Click here to apply")')
        df.drop(columns=['url'], inplace=True)

    if 'referral_url' in df.columns:
        df['linkedin referral'] = df['referral_url'].apply(
            lambda l: f'=HYPERLINK("{l}", "Find Referrals")' if pd.notnull(l) and l != "" else ""
        )
        df.drop(columns=['referral_url'], inplace=True)

    # Save locally first (in project root)
    file_path = os.path.abspath(filename)

    try:
        df.to_excel(file_path, index=False, engine='openpyxl')
    except Exception as e:
        return f"Error saving to Excel: {str(e)}"

    # Upload to Cloudinary
    upload_result = upload_excel_to_cloudinary(file_path, user_id)

    if "error" in upload_result:
        # File saved locally but Cloudinary failed — still inform user
        return (
            f"✅ Saved {len(jobs_data)} jobs locally at: {file_path}\n"
            f"⚠️ Cloudinary upload failed: {upload_result['error']}"
        )

    return (
        f"✅ Saved {len(jobs_data)} jobs to Excel.\n"
        f"☁️ Uploaded to Cloudinary for user '{upload_result['user_id']}'.\n"
        f"🔗 Download link: {upload_result['url']}"
    )
