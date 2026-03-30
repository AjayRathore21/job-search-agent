"""
Tool for reading and processing the user's resume.
Provides a tool for the agent to understand the user's skills.
"""

from pypdf import PdfReader
import os
from langchain_core.tools import tool

@tool
def read_resume(resume_path: str = "Ajay_resume.pdf") -> str:
    """
    Reads the content of the user's resume and returns the text.
    The agent can use this to understand the user's skills and experience.
    By default, it looks for Ajay_resume.pdf in the project root.
    """
    # Try different capitalizations
    paths_to_check = [resume_path, "Ajay_resume.pdf", "ajay_resume.pdf"]
    
    found_path = None
    for p in paths_to_check:
        if os.path.exists(p):
            found_path = p
            break
            
    if not found_path:
        return f"Error: Resume file not found at {resume_path}. Please check if the file name is correct."

    try:
        reader = PdfReader(found_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        
        return f"--- RESUME START ---\n{text}\n--- RESUME END ---"
    except Exception as e:
        return f"Error reading resume: {str(e)}"
