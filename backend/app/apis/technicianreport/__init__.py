from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.auth import AuthorizedUser
import databutton as db
from firebase_admin import firestore, auth  # type: ignore # <-- ADD 'auth' TO THIS IMPORT
from google.cloud.firestore_v1.base_query import FieldFilter  # type: ignore
from typing import List, Optional, Dict, Any
import datetime
from fastapi.concurrency import run_in_threadpool
from app.libs.gemini_client import get_gemini_client


# --- Router & AI Configuration ---
router = APIRouter(prefix="/technicianreport", tags=["technicianreport"])

print("Technician report API: Using centralized Gemini client.")


# --- Pydantic Models ---

class ReportGenerationRequest(BaseModel):
    """ The frontend only needs to send the session_id and any last-minute notes from the technician. """
    session_id: str
    technician_final_notes: Optional[str] = Field(None, description="Optional final voice or text notes from the technician.")

class ReportGenerationResponse(BaseModel):
    generated_report_markdown: str

class ReportSaveRequest(BaseModel):
    session_id: str
    report_markdown: str
    # latitude: float
    # longitude: float

class ReportSaveResponse(BaseModel):
    success: bool
    report_id: str

class ReportGetResponse(BaseModel):
    report_id: str
    session_id: str
    technician_uid: str
    company: str
    created_at: datetime.datetime
    #location: Dict[str, float]
    location: str 
    report_markdown: str

# --- FIX: Removed the orphaned ReportListResponse from the bottom of the file ---
# It was not being used and could cause import issues.


# --- API Endpoint to GENERATE the Report (REVISED LOGIC) ---

@router.post("/generate", response_model=ReportGenerationResponse)
async def generate_llm_draft_report(  # <-- ADD 'async' back here
    request: ReportGenerationRequest,
    user: AuthorizedUser
):
    """
    Takes a session_id, fetches the full session context from Firestore,
    and then uses Google Gemini to generate a professional report draft.
    """
    try:
        # Define a helper function for your blocking database calls
        def get_session_data():
            db_firestore = firestore.client()
            session_ref = db_firestore.collection('troubleshootingSessions').document(request.session_id)
            session_doc = session_ref.get()
            if not session_doc.exists:
                # You can't raise HTTPException here, so return None
                return None
            return session_doc.to_dict()

        # Await the blocking function in a separate thread
        session_data = await run_in_threadpool(get_session_data)

        if session_data is None:
            raise HTTPException(status_code=404, detail=f"Troubleshooting session with ID '{request.session_id}' not found.")

        # --- The rest of your data processing logic is perfect ---
        initial_problem = session_data.get('assignmentDescription', 'No problem description was recorded.')
        ai_recommendation = session_data.get('response', 'No AI recommendation was recorded.')
        gcs_paths = session_data.get('mediaGcsPaths', [])
        company_name = session_data.get('company', 'N/A')
        media_filenames = [path.split('/')[-1] for path in gcs_paths]
        technician_name = user.name or user.email

    except Exception as e:
        print(f"Error fetching session data from Firestore: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve session data from the database.")

    # --- Your AI call logic is also perfect ---
    model = get_gemini_client()
    prompt = f"""
    ROLE: You are a Senior Service Manager for the company "{company_name}".
    TASK: Write a formal, structured field service report based on the provided data from a troubleshooting session conducted by a technician.
    FORMAT: The output MUST be in Markdown and follow this structure exactly:

    # Field Service Report: Session {request.session_id}

    ### 1. Executive Summary
    A brief, one-paragraph overview of the reported issue, the diagnostic process, and the final resolution or recommendation.

    ### 2. Session Details
    - **Technician:** {technician_name}
    - **Company:** {company_name}
    - **Date of Service:** {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

    ### 3. Problem Description
    A detailed account of the initial problem as reported by the technician.

    ### 4. Diagnostic & Resolution Steps
    An explanation of the final recommendation provided by the AI assistant.

    ### 5. Supporting Evidence
    A list of all media files submitted during the session.

    ### 6. Technician's Final Observations
    Include any final notes or observations the technician added after the session.

    ---
    RAW DATA FOR REPORT GENERATION:
    - **Initial Problem Reported:** {initial_problem}
    - **AI Assistant's Recommendation:** {ai_recommendation}
    - **Submitted Media Files:** {', '.join(media_filenames) if media_filenames else 'None'}
    - **Technician's Final Notes:** {request.technician_final_notes or 'No additional notes were provided.'}
    ---

    Generate the complete report now.
    """

    try:
        response = model.generate_content(prompt, model='gemini-2.5-flash')
        return ReportGenerationResponse(generated_report_markdown=response)
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report from AI model.")


# --- API Endpoint to SAVE the Final Report (No Changes Needed) ---

@router.post("/save", response_model=ReportSaveResponse)
def save_finalized_report(
    request: ReportSaveRequest, # Uses the revised request model
    user: AuthorizedUser
):
    """
    Saves the final report. It now fetches the 'assignmentLocation' from the
    original troubleshooting session instead of receiving coordinates.
    """
    try:
        db_firestore = firestore.client()
        
        # 1. FETCH THE ORIGINAL SESSION DOCUMENT TO GET LOCATION
        session_ref = db_firestore.collection('troubleshootingSessions').document(request.session_id)
        session_doc = session_ref.get()
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail=f"Original session {request.session_id} not found.")
        
        session_data = session_doc.to_dict()
        assignment_location = session_data.get('assignmentLocation', 'Not specified')

        # 2. PREPARE THE NEW REPORT DATA
        # --- FIX STARTS HERE ---
        # Get the full user record from Firebase to access custom claims
        try:
            full_user_record = auth.get_user(user.sub)
            company = full_user_record.custom_claims.get('company', 'Unknown')
        except Exception as e:
            print(f"Error fetching full user record for {user.sub}: {e}")
            company = "Unknown" # Fallback company
        # --- FIX ENDS HERE ---

        report_data = {
            'technician_uid': user.sub,
            'company': company,
            'session_id': request.session_id,
            'created_at': firestore.SERVER_TIMESTAMP,
            'report_markdown': request.report_markdown,
            'location': assignment_location, # Use the string location from the session
        }

        # 3. SAVE THE NEW REPORT
        _, report_ref = db_firestore.collection('troubleshootingReports').add(report_data)

        return ReportSaveResponse(success=True, report_id=report_ref.id)
    except Exception as e:
        print(f"Error saving report to Firestore: {e}")
        raise HTTPException(status_code=500, detail="Could not save report to the database.")


# --- (NEW ENDPOINT WITH FIXES) ---
@router.get("/my-reports", response_model=List[ReportGetResponse], operation_id="get_my_reports")
def get_my_reports(user: AuthorizedUser):
    """
    Retrieves all troubleshooting reports filed by the currently authenticated technician,
    ordered from newest to oldest.
    """
    try:
        db_firestore = firestore.client()

        # --- FIX: The query now correctly uses 'technician_uid' and valid syntax. ---
        reports_query = db_firestore.collection('troubleshootingReports').where(
            filter=FieldFilter('technician_uid', '==', user.sub)
        ).order_by(
            'created_at', direction=firestore.Query.DESCENDING
        )

        results = reports_query.stream()

        reports_list = []
        for doc in results:
            report_data = doc.to_dict()
            reports_list.append(
                ReportGetResponse(
                    report_id=doc.id,
                    session_id=report_data.get('session_id'),
                    technician_uid=report_data.get('technician_uid'),
                    company=report_data.get('company'),
                    created_at=report_data.get('created_at'),
                    location=report_data.get('location', 'Location not specified'),
                    report_markdown=report_data.get('report_markdown'),
                )
            )

        return reports_list

    except Exception as e:
        print(f"Error retrieving reports for technician {user.sub}: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving your reports.")


# --- API Endpoint to RETRIEVE a Report (No Changes Needed) ---

@router.get("/{report_id}", response_model=ReportGetResponse)
def get_specific_report(report_id: str, user: AuthorizedUser):
    """ Retrieves a single troubleshooting report by its document ID from Firestore. """
    try:
        db_firestore = firestore.client()
        report_ref = db_firestore.collection('troubleshootingReports').document(report_id)
        report_doc = report_ref.get()

        if not report_doc.exists:
            raise HTTPException(status_code=404, detail="Report not found.")

        report_data = report_doc.to_dict()
        
        # --- FIX: user.custom_claims is not available, using get_user to fetch them ---
        full_user_record = auth.get_user(user.sub)
        user_role = full_user_record.custom_claims.get('role')
        user_company = full_user_record.custom_claims.get('company')

        if user_role != 'system_admin' and report_data.get('company') != user_company:
            raise HTTPException(status_code=403, detail="You do not have permission to view this report.")

        # REVISED: Directly get the location string
        location_str = report_data.get('location', 'Location not specified')

        return ReportGetResponse(
            report_id=report_doc.id,
            session_id=report_data.get('session_id'),
            technician_uid=report_data.get('technician_uid'),
            company=report_data.get('company'),
            created_at=report_data.get('created_at'),
            location=location_str, # <-- Pass the string directly
            report_markdown=report_data.get('report_markdown'),
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error retrieving report {report_id}: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving the report.")
