"""
Tool to save data into Excel files.
"""

import pandas as pd
import os
from datetime import datetime
from langchain_core.tools import tool

@tool
def save_jobs_to_excel(jobs_data: list[dict], filename: str | None = None) -> str:
    """
    Saves a list of job dictionaries (title and url) to an Excel file.
    Returns the path to the saved file.

    Args:
        jobs_data: A list of dictionaries like [{"title": "...", "url": "..."}]
        filename: Optional custom filename. Defaults to jobs_YYYYMMDD_HHMMSS.xlsx
    """
    if not jobs_data:
        return "Error: No data provided."

    # Create filename if not provided
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"jobs_{timestamp}.xlsx"

    # Convert to DataFrame
    df = pd.DataFrame(jobs_data)

    # Make URLs clickable in Excel using =HYPERLINK formula
    if 'url' in df.columns:
        df['url'] = df['url'].apply(lambda x: f'=HYPERLINK("{x}", "Click here to apply")')

    if 'referral_url' in df.columns:
        df['referral_url'] = df['referral_url'].apply(lambda l: f'=HYPERLINK("{l}", "Find Referrals")')

    # Make path absolute
    # By default, save in the current project root
    file_path = os.path.abspath(filename)

    try:
        # Save to Excel with openpyxl engine
        df.to_excel(file_path, index=False, engine='openpyxl')
        return f"Successfully saved {len(jobs_data)} matching jobs with match summaries and referral info to {file_path}"
    except Exception as e:
        return f"Error saving to Excel: {str(e)}"
