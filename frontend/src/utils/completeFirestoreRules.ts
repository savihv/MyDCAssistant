export const completeFirestoreRules = `
rules_version = '2';

service cloud.firestore {
  match /databases/{database}/documents {
    // HELPER FUNCTIONS
    function isSystemAdmin() {
      return request.auth != null && request.auth.token.role == 'system_admin';
    }
    function isCompanyAdmin() {
      return request.auth != null && request.auth.token.role == 'company_admin';
    }
    function isTechnician() {
      return request.auth != null && request.auth.token.role == 'technician';
    }
    function isAuthenticated() {
      return request.auth != null;
    }
    function isOwner(userId) {
      // Ensure request.auth is not null before accessing uid
      return request.auth != null && request.auth.uid == userId;
    }
    
    // USER MANAGEMENT
    match /users/{userId} {
      allow read: if isSystemAdmin() || 
                   isOwner(userId) || 
                   (isCompanyAdmin() && resource.data.company == request.auth.token.company);
      allow write: if isSystemAdmin() || isOwner(userId); 
    }

    // SETTINGS MANAGEMENT
    match /settings/{settingId} {
      allow read, write: if isSystemAdmin() ||
                          (isCompanyAdmin() && settingId == request.auth.token.company);
    }
    
    // COMPANY MANAGEMENT
    match /companies/{companyDocId} {
      // Consideration: If company data is sensitive, you might restrict read to isCompanyAdmin() instead of isAuthenticated()
      allow read: if isSystemAdmin() || 
                   (isAuthenticated() && companyDocId == request.auth.token.company); 
      allow write: if isSystemAdmin() || 
                    (isCompanyAdmin() && companyDocId == request.auth.token.company && request.resource.data.id == request.auth.token.company); 
    }
    
    // PENDING USER REQUESTS
    match /pendingRequests/{requestId} {
      allow create: if isAuthenticated(); 
      allow read, update: if isSystemAdmin() || 
                           (isCompanyAdmin() && resource.data.company == request.auth.token.company);
      allow delete: if isSystemAdmin(); 
    }
    
    // DOCUMENTS & KNOWLEDGE BASE
    match /documents/{docId} {
      allow read: if isSystemAdmin() || 
                   (isAuthenticated() && resource.data.company == request.auth.token.company && (isCompanyAdmin() || isTechnician()));
      allow write: if isSystemAdmin() || 
                    (isCompanyAdmin() && 
                     request.resource.data.company == request.auth.token.company &&
                     (request.method == 'create' || (request.method == 'update' && resource.data.company == request.auth.token.company))
                    );
      allow delete: if isSystemAdmin() || (isCompanyAdmin() && resource.data.company == request.auth.token.company); 
    }
    
    // TROUBLESHOOTING SESSIONS
    match /troubleshootingSessions/{sessionId} {

      // CREATE: Technicians can create sessions for themselves and their company.
      allow create: if isTechnician() &&
                       request.resource.data.userId == request.auth.uid && 
                       request.resource.data.company == request.auth.token.company &&
                       request.resource.data.assignmentName is string && request.resource.data.assignmentName.size() > 0 &&
                       request.resource.data.assignmentDescription is string && request.resource.data.assignmentDescription.size() > 0 &&
                       request.resource.data.status == 'new' &&
                       request.resource.data.timestamp is timestamp && 
                       request.resource.data.lastUpdated is timestamp && 
                       request.resource.data.userId is string && 
                       request.resource.data.company is string &&
                       request.resource.data.keys().hasOnly([
                         'userId', 'company', 'assignmentName', 'assignmentLocation',
                         'assignmentDescription', 'timestamp', 'lastUpdated', 'status'
                       ]) &&
                       (request.resource.data.assignmentLocation == null || request.resource.data.assignmentLocation is string);

      // READ: System admins, company admins (for their company's sessions), or the technician who owns the session.
      allow read: if isSystemAdmin() ||
                   (isCompanyAdmin() && resource.data.company == request.auth.token.company) ||
                   (isTechnician() && resource.data.userId == request.auth.uid);
                   
      // UPDATE: Technicians can update their own sessions.
      allow update: if isTechnician() && resource.data.userId == request.auth.uid;
                     
      // DELETE: Allow System Admins or the Technician owner to delete.
      allow delete: if isSystemAdmin() || (isTechnician() && resource.data.userId == request.auth.uid);

      // VOICECOMMANDS SUBCOLLECTION
      match /voiceCommands/{commandId} {
        function getParentSessionData() {
          return get(/databases/$(database)/documents/troubleshootingSessions/$(sessionId)).data;
        }

        allow create: if isTechnician() &&
                         request.resource.data.userId == request.auth.uid &&
                         exists(/databases/$(database)/documents/troubleshootingSessions/$(sessionId)) && 
                         getParentSessionData().userId == request.auth.uid &&
                         getParentSessionData().company == request.auth.token.company &&
                         request.resource.data.keys().hasOnly(['transcription', 'timestamp', 'userId']) &&
                         request.resource.data.transcription is string && request.resource.data.transcription.size() > 0 &&
                         request.resource.data.timestamp is timestamp;
        
        allow read: if isSystemAdmin() ||
                     (isCompanyAdmin() && exists(/databases/$(database)/documents/troubleshootingSessions/$(sessionId)) && getParentSessionData().company == request.auth.token.company) ||
                     (isTechnician() && exists(/databases/$(database)/documents/troubleshootingSessions/$(sessionId)) && getParentSessionData().userId == request.auth.uid && getParentSessionData().company == request.auth.token.company);
      }
    }
    
    // MODERATION QUEUE
    match /moderationQueue/{itemId} {
      allow read: if isSystemAdmin() ||
                     (isCompanyAdmin() && resource.data.company == request.auth.token.company); 
      allow write: if isSystemAdmin() ||
                      (isCompanyAdmin() && 
                        ( (request.method == 'create' && request.resource.data.company == request.auth.token.company) ||
                          (request.method == 'update' && resource.data.company == request.auth.token.company && request.resource.data.company == request.auth.token.company) 
                        )
                      );
      allow delete: if isSystemAdmin();
    }

    // EXPLICIT DEFAULT DENY (Best Practice)
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
`;
