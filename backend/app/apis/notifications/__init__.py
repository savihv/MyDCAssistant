from typing import Dict, Optional, List
from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.auth import AuthorizedUser
import databutton as db
import re

# Initialize the router
router = APIRouter()

# Pydantic models for requests and responses
class EmailRequest(BaseModel):
    to: EmailStr
    subject: str
    content_text: str
    content_html: Optional[str] = None

class EmailResponse(BaseModel):
    success: bool
    message: str

# Helper function to send email notifications
def send_email_notification(to: str, subject: str, content_text: str, content_html: Optional[str] = None):
    try:
        db.notify.email(
            to=to,
            subject=subject,
            content_text=content_text,
            content_html=content_html or content_text.replace('\n', '<br>'),
        )
        print(f"Email notification sent to {to}")
        return True
    except Exception as e:
        print(f"Error sending email notification: {e}")
        return False

# Send email notification endpoint - protected, admin only
@router.post("/send-email")
async def send_email(user: AuthorizedUser, background_tasks: BackgroundTasks, request: EmailRequest) -> EmailResponse:
    try:
        # Add task to background to avoid blocking the response
        background_tasks.add_task(
            send_email_notification,
            to=request.to,
            subject=request.subject,
            content_text=request.content_text,
            content_html=request.content_html
        )
        
        return EmailResponse(
            success=True,
            message="Email notification queued successfully"
        )
    except Exception as e:
        print(f"Error queuing email notification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to queue email notification: {str(e)}")

# Function to send approval notification
def send_approval_notification(user_email: str, user_name: str, role: str, company: Optional[str] = None):
    subject = "Your JuniorTechBot Account Has Been Approved"
    
    # Create the message based on the role
    if role == "company_admin":
        content_text = f"""Hello {user_name},

Your request for a Company Admin account at JuniorTechBot has been approved!

You now have access to:
- Upload company-specific documents to the knowledge base
- Manage technicians in your company
- View analytics and usage statistics

You can log in now at: https://juniortechbot.riff.works/techassist

Thank you for choosing JuniorTechBot.

Best regards,
The JuniorTechBot Team
"""
    else:  # technician
        company_line = f"for {company}" if company else ""
        content_text = f"""Hello {user_name},

Your request for a Technician account {company_line} at JuniorTechBot has been approved!

You now have access to:
- Submit technical questions using voice, text, or images
- Get AI-powered troubleshooting assistance
- Access company-specific knowledge base

You can log in now at: https://juniortechbot.riff.works/techassist

Thank you for choosing JuniorTechBot.

Best regards,
The JuniorTechBot Team
"""
    
    # HTML version with basic formatting
    content_html = content_text.replace('\n\n', '</p><p>')
    content_html = f"<html><body><p>{content_html}</p></body></html>"
    
    return send_email_notification(
        to=user_email,
        subject=subject,
        content_text=content_text,
        content_html=content_html
    )

# Function to send rejection notification
def send_rejection_notification(user_email: str, user_name: str, role: str, reason: str, company: Optional[str] = None):
    subject = "Update on Your JuniorTechBot Account Request"
    
    # Create the message based on the role
    role_display = "Company Admin" if role == "company_admin" else "Technician"
    company_line = f"for {company}" if company else ""
    
    content_text = f"""Hello {user_name},

We've reviewed your request for a {role_display} account {company_line} at JuniorTechBot.

Unfortunately, we are unable to approve your request at this time for the following reason:

{reason}

If you believe this is an error or would like to provide additional information, please contact your administrator.

Thank you for your interest in JuniorTechBot.

Best regards,
The JuniorTechBot Team
"""
    
    # HTML version with basic formatting
    content_html = content_text.replace('\n\n', '</p><p>')
    content_html = f"<html><body><p>{content_html}</p></body></html>"
    
    return send_email_notification(
        to=user_email,
        subject=subject,
        content_text=content_text,
        content_html=content_html
    )
