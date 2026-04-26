import {
  ActivateCustomerData,
  AddExpertEntryToKnowledgeBaseData,
  AddSessionRequest,
  AddSessionToKnowledgeBaseData,
  ApproveExpertTipData,
  ApproveRejectRequest,
  ApproveRejectUserData,
  AssignDomainRequest,
  AssignUserDomainData,
  BodyGetCsvHeaders,
  BodyTranscribeAudio,
  BodyUploadAssetInventory,
  BodyUploadDocument,
  BodyUploadGeneralFile,
  BodyUploadHistoricRecordsCsv,
  BodyUploadSchematicFile,
  BodyUploadTechnicianFileV2,
  BodyUploadZipArchive,
  BodyValidateBomUpload,
  BootstrapControlPlaneEndpointData,
  BootstrapRequest,
  BulkDeleteHistoricRecordsData,
  BulkDeleteHistoricRecordsRequest,
  CablingValidationRequest,
  CheckHealthData,
  CheckQuotaData,
  ConfigureSchematicProcessingData,
  ConstraintCreate,
  ConstraintUpdate,
  CreateCustomerData,
  CreateCustomerRequest,
  CreateExpertTipEntryData,
  CreateExpertTipEntryRequest,
  CreateNewConstraintData,
  DHCPDiscoverRequest,
  DeleteCustomerData,
  DeleteDocumentData,
  DeleteExistingConstraintData,
  DeleteExpertTipFromKnowledgeBaseData,
  DeleteHistoricRecordData,
  DeleteProjectData,
  DeleteSessionFromKnowledgeBaseData,
  DeleteSessionRequest,
  DhcpDiscoveryWebhookData,
  DirectApproveRequest,
  DirectApproveUser2Data,
  DirectApproveUserData,
  DirectRegistrationRequest,
  DiscoveryReport,
  DocumentUpdateRequest,
  DownloadAssetTemplateData,
  DownloadTestCsvData,
  DownloadTestSchematicData,
  EmailRequest,
  EmergencyOverrideData,
  EmergencyOverrideRequest,
  ExpertKnowledgeRequest,
  ExpertTipRequest,
  ExportCablingMatrixData,
  FeedbackTranscriptionRequest,
  FirebaseStatusData,
  GenerateConfigRequest,
  GenerateLlmDraftReportData,
  GenerateOnboardingConfigsData,
  GenerateResponseData,
  GetAdminMetricsData,
  GetAllUsersData,
  GetAvailableConstraintTemplatesData,
  GetAvailableDomainsData,
  GetClusterReadinessData,
  GetClusterStatusData,
  GetCompanyNamespacesEndpointData,
  GetCsvHeadersData,
  GetCustomerData,
  GetDiscoveryScriptData,
  GetDocumentData,
  GetDocumentMetricsSummaryData,
  GetDocumentOptimalData,
  GetDocumentStatusData,
  GetExtractionResultsData,
  GetFullZtpConfigData,
  GetIpAllocationPreviewData,
  GetMergeValidationData,
  GetMyReportsData,
  GetNodeDetailsData,
  GetNodeTopologyData,
  GetPendingUsersData,
  GetProcessingStatusData,
  GetProvisioningAlertsData,
  GetProvisioningStatusData,
  GetSecureDocumentUrlData,
  GetSecureMediaUrlsForTipData,
  GetSpecificReportData,
  GetTierHealthData,
  HandleDiscoveryCallbackData,
  HandleZtpCompletionData,
  ImportConstraintTemplatesData,
  ImportTemplatesRequest,
  JoinNodeRequest,
  JoinWorkerNodeData,
  ListClusterNodesData,
  ListConstraintsData,
  ListCustomersData,
  ListDeploymentTemplatesData,
  ListDocumentsData,
  ListHistoricRecordsData,
  ListProjectsData,
  ProcessDocumentWorkerData,
  RegisterUserData,
  RejectExpertTipData,
  ReportGenerationRequest,
  ReportSaveRequest,
  ReprocessRequest,
  ReprocessStuckDocumentData,
  ResolveAlertRequest,
  ResolveProvisioningAlertData,
  ResponseRequest,
  RetrievalRequest,
  RetrieveKnowledgeData,
  SaveFinalizedReportData,
  SchematicConfigRequest,
  SearchWebData,
  SendEmailData,
  StreamAudioFileData,
  SuspendCustomerData,
  SuspendCustomerRequest,
  SyncSingleNodeData,
  SyncTopologyData,
  SynthesisRequest,
  SynthesizeData,
  TranscribeAudioData,
  TranscribeAudioOptionsData,
  TranscribeFeedbackData,
  UpdateCustomerData,
  UpdateCustomerRequest,
  UpdateDocumentData,
  UpdateExistingConstraintData,
  UpgradeLicenseData,
  UpgradeLicenseRequest,
  UploadAssetInventoryData,
  UploadDocumentData,
  UploadGeneralFileData,
  UploadHistoricRecordsCsvData,
  UploadSchematicFileData,
  UploadTechnicianFileV2Data,
  UploadZipArchiveData,
  UserRegistrationRequest,
  ValidateBomUploadData,
  ValidateCablingData,
  VerifySyncData,
  WebSearchRequest,
  WorkerPayload,
  ZTPCompletionRequest,
} from "./data-contracts";

export namespace Apiclient {
  /**
   * @description Check health of application. Returns 200 when OK, 500 when not.
   * @name check_health
   * @summary Check Health
   * @request GET:/_healthz
   */
  export namespace check_health {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = CheckHealthData;
  }

  /**
   * @description Adds a specific user session's Q&A to the knowledge base.
   * @tags knowledge_base, dbtn/module:knowledge_base, dbtn/hasAuth
   * @name add_session_to_knowledge_base
   * @summary Add Session To Knowledge Base
   * @request POST:/routes/add-session-to-knowledge-base
   */
  export namespace add_session_to_knowledge_base {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = AddSessionRequest;
    export type RequestHeaders = {};
    export type ResponseBody = AddSessionToKnowledgeBaseData;
  }

  /**
   * No description
   * @tags dbtn/module:knowledge_base, dbtn/hasAuth
   * @name add_expert_entry_to_knowledge_base
   * @summary Add Expert Entry To Knowledge Base
   * @request POST:/routes/add-expert-entry-to-knowledge-base
   */
  export namespace add_expert_entry_to_knowledge_base {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = ExpertKnowledgeRequest;
    export type RequestHeaders = {};
    export type ResponseBody = AddExpertEntryToKnowledgeBaseData;
  }

  /**
   * @description Deletes a session's vector from Pinecone and updates Firestore.
   * @tags dbtn/module:knowledge_base, dbtn/hasAuth
   * @name delete_session_from_knowledge_base
   * @summary Delete Session From Knowledge Base
   * @request DELETE:/routes/delete-session-from-knowledge-base
   */
  export namespace delete_session_from_knowledge_base {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = DeleteSessionRequest;
    export type RequestHeaders = {};
    export type ResponseBody = DeleteSessionFromKnowledgeBaseData;
  }

  /**
   * @description Approves an expert tip, processes its content and media, generates an embedding, and adds it to the company's Pinecone knowledge base.
   * @tags knowledge_base, expert_tips, dbtn/module:knowledge_base, dbtn/hasAuth
   * @name approve_expert_tip
   * @summary Approve Expert Tip
   * @request POST:/routes/approve_expert_tip
   */
  export namespace approve_expert_tip {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = ExpertTipRequest;
    export type RequestHeaders = {};
    export type ResponseBody = ApproveExpertTipData;
  }

  /**
   * @description Rejects an expert tip. If it was previously approved and added to the knowledge base, removes it from Pinecone before updating the status to 'rejected'.
   * @tags knowledge_base, expert_tips, dbtn/module:knowledge_base, dbtn/hasAuth
   * @name reject_expert_tip
   * @summary Reject Expert Tip
   * @request POST:/routes/reject_expert_tip
   */
  export namespace reject_expert_tip {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = ExpertTipRequest;
    export type RequestHeaders = {};
    export type ResponseBody = RejectExpertTipData;
  }

  /**
   * @description Deletes an approved expert tip from the Pinecone knowledge base and updates its status in Firestore to 'deleted'.
   * @tags knowledge_base, expert_tips, dbtn/module:knowledge_base, dbtn/hasAuth
   * @name delete_expert_tip_from_knowledge_base
   * @summary Delete Expert Tip From Knowledge Base
   * @request POST:/routes/delete_expert_tip_from_knowledge_base
   */
  export namespace delete_expert_tip_from_knowledge_base {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = ExpertTipRequest;
    export type RequestHeaders = {};
    export type ResponseBody = DeleteExpertTipFromKnowledgeBaseData;
  }

  /**
   * @description Streams an audio file stored in db.storage.binary.
   * @tags stream, dbtn/module:audio_files, dbtn/hasAuth
   * @name stream_audio_file
   * @summary Stream Audio File
   * @request GET:/routes/audio_files/stream/{filename}
   */
  export namespace stream_audio_file {
    export type RequestParams = {
      /** Filename */
      filename: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = StreamAudioFileData;
  }

  /**
   * No description
   * @tags dbtn/module:transcription, dbtn/hasAuth
   * @name transcribe_audio
   * @summary Transcribe Audio
   * @request POST:/routes/transcribe-audio
   */
  export namespace transcribe_audio {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = BodyTranscribeAudio;
    export type RequestHeaders = {};
    export type ResponseBody = TranscribeAudioData;
  }

  /**
   * @description Handle OPTIONS preflight requests for /transcribe-audio for CORS.
   * @tags dbtn/module:transcription, dbtn/hasAuth
   * @name transcribe_audio_options
   * @summary Transcribe Audio Options
   * @request OPTIONS:/routes/transcribe-audio
   */
  export namespace transcribe_audio_options {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = TranscribeAudioOptionsData;
  }

  /**
   * No description
   * @tags Zip Importer, dbtn/module:zip_importer, dbtn/hasAuth
   * @name upload_zip_archive
   * @summary Upload Zip Archive
   * @request POST:/routes/zip-importer/upload
   */
  export namespace upload_zip_archive {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = BodyUploadZipArchive;
    export type RequestHeaders = {};
    export type ResponseBody = UploadZipArchiveData;
  }

  /**
   * @description Handles general-purpose file uploads using the Firebase Admin SDK. This ensures consistent authentication with the rest of the application.
   * @tags Uploads, dbtn/module:uploads, dbtn/hasAuth
   * @name upload_general_file
   * @summary Upload General File
   * @request POST:/routes/uploads/upload_general_file
   */
  export namespace upload_general_file {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = BodyUploadGeneralFile;
    export type RequestHeaders = {};
    export type ResponseBody = UploadGeneralFileData;
  }

  /**
   * @description Search the web for relevant technical discussions based on the query
   * @tags dbtn/module:web_search, dbtn/hasAuth
   * @name search_web
   * @summary Search Web
   * @request POST:/routes/search
   */
  export namespace search_web {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = WebSearchRequest;
    export type RequestHeaders = {};
    export type ResponseBody = SearchWebData;
  }

  /**
   * @description Reads the header row of a CSV file and returns the column names. This is used to populate the column mapping interface on the frontend.
   * @tags importer, dbtn/module:importer, dbtn/hasAuth
   * @name get_csv_headers
   * @summary Get Csv Headers
   * @request POST:/routes/importer/get-csv-headers
   */
  export namespace get_csv_headers {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = BodyGetCsvHeaders;
    export type RequestHeaders = {};
    export type ResponseBody = GetCsvHeadersData;
  }

  /**
   * @description Accepts a CSV, validates it, imports to Firestore, and creates/stores embeddings in the correct company-specific Pinecone index.
   * @tags importer, dbtn/module:importer, dbtn/hasAuth
   * @name upload_historic_records_csv
   * @summary Upload Historic Records Csv
   * @request POST:/routes/importer/upload-historic-records-csv
   */
  export namespace upload_historic_records_csv {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = BodyUploadHistoricRecordsCsv;
    export type RequestHeaders = {};
    export type ResponseBody = UploadHistoricRecordsCsvData;
  }

  /**
   * @description Deletes a single historic record from Firestore and Pinecone.
   * @tags importer, dbtn/module:importer, dbtn/hasAuth
   * @name delete_historic_record
   * @summary Delete Historic Record
   * @request DELETE:/routes/importer/historic-records/{record_id}
   */
  export namespace delete_historic_record {
    export type RequestParams = {
      /** Record Id */
      recordId: string;
    };
    export type RequestQuery = {
      /**
       * Target Index
       * @default "historic"
       */
      target_index?: string;
    };
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = DeleteHistoricRecordData;
  }

  /**
   * @description Deletes multiple historic records from Firestore and Pinecone.
   * @tags importer, dbtn/module:importer, dbtn/hasAuth
   * @name bulk_delete_historic_records
   * @summary Bulk Delete Historic Records
   * @request POST:/routes/importer/bulk-delete-historic-records
   */
  export namespace bulk_delete_historic_records {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = BulkDeleteHistoricRecordsRequest;
    export type RequestHeaders = {};
    export type ResponseBody = BulkDeleteHistoricRecordsData;
  }

  /**
   * @description Lists historic records for the user's company.
   * @tags importer, dbtn/module:importer, dbtn/hasAuth
   * @name list_historic_records
   * @summary List Historic Records
   * @request GET:/routes/importer/historic-records
   */
  export namespace list_historic_records {
    export type RequestParams = {};
    export type RequestQuery = {
      /**
       * Target Index
       * @default "historic"
       */
      target_index?: string;
      /**
       * Limit
       * @default 50
       */
      limit?: number;
      /**
       * Offset
       * @default 0
       */
      offset?: number;
    };
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = ListHistoricRecordsData;
  }

  /**
   * @description Transcribe audio feedback using Google Cloud Speech-to-Text
   * @tags dbtn/module:feedback, dbtn/hasAuth
   * @name transcribe_feedback
   * @summary Transcribe Feedback
   * @request POST:/routes/transcribe-feedback
   */
  export namespace transcribe_feedback {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = FeedbackTranscriptionRequest;
    export type RequestHeaders = {};
    export type ResponseBody = TranscribeFeedbackData;
  }

  /**
   * No description
   * @tags dbtn/module:notifications, dbtn/hasAuth
   * @name send_email
   * @summary Send Email
   * @request POST:/routes/send-email
   */
  export namespace send_email {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = EmailRequest;
    export type RequestHeaders = {};
    export type ResponseBody = SendEmailData;
  }

  /**
   * No description
   * @tags dbtn/module:response_generation, dbtn/hasAuth
   * @name generate_response
   * @summary Generate Response
   * @request POST:/routes/generate-response
   */
  export namespace generate_response {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = ResponseRequest;
    export type RequestHeaders = {};
    export type ResponseBody = GenerateResponseData;
  }

  /**
   * @description Stage 1: Receive serial number report from switch. Called by discovery script running on switch during initial boot. Verifies hardware identity and prepares full ZTP configuration. Args: body: Discovery report with MAC, serial, and optional vendor/model Returns: Discovery response with verification status and next steps Example Request: POST /ztp/discovery { "mac": "00:1B:21:D9:56:E3", "serial": "NVDA-QM9700-SP01-2024", "vendor": "NVIDIA", "model": "QM9700" } Example Response (Success): { "status": "VERIFIED", "message": "Identity verified. Ready for configuration.", "next_step": "https://yourapp.com/ztp/config/00:1B:21:D9:56:E3", "device_name": "IB-SPINE-01", "assigned_ip": "10.0.4.250" }
   * @tags dbtn/module:ztp
   * @name handle_discovery_callback
   * @summary Handle Discovery Callback
   * @request POST:/routes/ztp/discovery
   */
  export namespace handle_discovery_callback {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = DiscoveryReport;
    export type RequestHeaders = {};
    export type ResponseBody = HandleDiscoveryCallbackData;
  }

  /**
   * @description Stage 2: Provide full configuration script to verified switch. Called by switch after identity verification succeeds. Returns vendor-specific configuration script with all port IPs. Args: mac_address: MAC address of verified switch Returns: ConfigScriptResponse with bash script content Raises: HTTPException: If switch not verified or config not ready Example Request: GET /ztp/config/00:1B:21:D9:56:E3 Example Response: { "script": "#!/bin/bash cli configure terminal ...", "device_name": "IB-SPINE-01", "vendor": "NVIDIA", "model": "QM9700", "status": "READY" }
   * @tags dbtn/module:ztp
   * @name get_full_ztp_config
   * @summary Get Full Ztp Config
   * @request GET:/routes/ztp/config/{mac_address}
   */
  export namespace get_full_ztp_config {
    export type RequestParams = {
      /** Mac Address */
      macAddress: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetFullZtpConfigData;
  }

  /**
   * @description Generate minimal discovery script for unconfigured switch. This is the initial script sent via DHCP Option 67 that extracts the serial number and reports it back to the API. Args: mac_address: MAC address of switch (from DHCP request) Returns: Bash script as plain text Example Response: #!/bin/bash SERIAL=$(dmidecode -s system-serial-number) curl -X POST https://yourapp.com/ztp/discovery \ -d '{"mac":"00:1B:...","serial":"$SERIAL"}'
   * @tags dbtn/module:ztp
   * @name get_discovery_script
   * @summary Get Discovery Script
   * @request GET:/routes/ztp/discovery-script/{mac_address}
   */
  export namespace get_discovery_script {
    export type RequestParams = {
      /** Mac Address */
      macAddress: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetDiscoveryScriptData;
  }

  /**
   * @description Validate physical cabling against GPU-aware topology expectations. This is the critical "Verification" phase. After the switch executes its ZTP configuration and enables LLDP, it reports what neighbors it actually sees. We compare this against the expected GPU-to-Leaf mapping to detect mis-wires. **Why This Matters:** In a 4K GPU cluster with 32,768 cables, a single mis-wire causes: - ❌ 15-40% degradation in All-Reduce operations - ❌ Cross-plane traffic (defeats InfiniBand rail isolation) - ❌ Discovered only during expensive training runs ($50K+ delay) **This API Prevents:** - Wrong cables (Port 1 has Port 2's GPU) - Cross-rack errors (Rack 1 GPU on Rack 2 port) - Missing cables (expected connection, but no LLDP neighbor) Args: body: Cabling validation request with switch ID and LLDP neighbor list Returns: Validation report with per-port status and health percentage Example Request: POST /validate-cabling { "switch_id": "IB-LEAF-P0-L01", "plane_id": 0, "leaf_id": 1, "neighbors": [ {"port_id": "p1", "neighbor_hostname": "B200-Rack01-Srv01-GPU1-HCA0"}, {"port_id": "p2", "neighbor_hostname": "B200-Rack01-Srv02-GPU1-HCA0"} ] } Example Response (Mis-wire Detected): { "status": "COMPLETE", "cluster_healthy": false, "failed": 2, "swap_recommendations": ["🔄 Swap cables: Port 1 ↔ Port 2"] }
   * @tags dbtn/module:ztp
   * @name validate_cabling
   * @summary Validate Cabling
   * @request POST:/routes/validate-cabling
   */
  export namespace validate_cabling {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = CablingValidationRequest;
    export type RequestHeaders = {};
    export type ResponseBody = ValidateCablingData;
  }

  /**
   * @description Upload a data center schematic for processing
   * @tags dbtn/module:cluster_bringup
   * @name upload_schematic_file
   * @summary Upload Schematic File
   * @request POST:/routes/cluster-bringup/upload-schematic
   */
  export namespace upload_schematic_file {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = BodyUploadSchematicFile;
    export type RequestHeaders = {};
    export type ResponseBody = UploadSchematicFileData;
  }

  /**
   * @description Configure color legend and processing options
   * @tags dbtn/module:cluster_bringup
   * @name configure_schematic_processing
   * @summary Configure Schematic Processing
   * @request POST:/routes/cluster-bringup/configure-processing
   */
  export namespace configure_schematic_processing {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = SchematicConfigRequest;
    export type RequestHeaders = {};
    export type ResponseBody = ConfigureSchematicProcessingData;
  }

  /**
   * @description Get current processing status
   * @tags dbtn/module:cluster_bringup
   * @name get_processing_status
   * @summary Get Processing Status
   * @request GET:/routes/cluster-bringup/processing-status/{project_id}
   */
  export namespace get_processing_status {
    export type RequestParams = {
      /** Project Id */
      projectId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetProcessingStatusData;
  }

  /**
   * @description Get extracted devices and connections
   * @tags dbtn/module:cluster_bringup
   * @name get_extraction_results
   * @summary Get Extraction Results
   * @request GET:/routes/cluster-bringup/extraction-results/{project_id}
   */
  export namespace get_extraction_results {
    export type RequestParams = {
      /** Project Id */
      projectId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetExtractionResultsData;
  }

  /**
   * @description Export cabling matrix as CSV
   * @tags dbtn/module:cluster_bringup
   * @name export_cabling_matrix
   * @summary Export Cabling Matrix
   * @request GET:/routes/cluster-bringup/export-cabling-matrix/{project_id}
   */
  export namespace export_cabling_matrix {
    export type RequestParams = {
      /** Project Id */
      projectId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = ExportCablingMatrixData;
  }

  /**
   * @description List all cluster bringup projects
   * @tags dbtn/module:cluster_bringup
   * @name list_projects
   * @summary List Projects
   * @request GET:/routes/cluster-bringup/projects
   */
  export namespace list_projects {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = ListProjectsData;
  }

  /**
   * @description Delete a cluster bringup project and all associated data
   * @tags dbtn/module:cluster_bringup
   * @name delete_project
   * @summary Delete Project
   * @request DELETE:/routes/cluster-bringup/project/{project_id}
   */
  export namespace delete_project {
    export type RequestParams = {
      /** Project Id */
      projectId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = DeleteProjectData;
  }

  /**
   * @description Upload asset inventory CSV and merge with extracted devices based on location hierarchy. Expected CSV columns: - Site, Room, Row, Rack, U-Position (or UPosition) - Serial Number (or SerialNumber) - Asset Tag (or AssetTag) - Manufacturer - Model - MAC Address (optional) - Purchase Date (optional) - Warranty Expiry (optional)
   * @tags dbtn/module:cluster_bringup
   * @name upload_asset_inventory
   * @summary Upload Asset Inventory
   * @request POST:/routes/cluster-bringup/upload-asset-inventory/{project_id}
   */
  export namespace upload_asset_inventory {
    export type RequestParams = {
      /** Project Id */
      projectId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = BodyUploadAssetInventory;
    export type RequestHeaders = {};
    export type ResponseBody = UploadAssetInventoryData;
  }

  /**
   * @description Get validation report showing which devices have been verified against asset inventory.
   * @tags dbtn/module:cluster_bringup
   * @name get_merge_validation
   * @summary Get Merge Validation
   * @request GET:/routes/cluster-bringup/merge-validation/{project_id}
   */
  export namespace get_merge_validation {
    export type RequestParams = {
      /** Project Id */
      projectId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetMergeValidationData;
  }

  /**
   * @description Download a sample CSV template for asset inventory with network-specific columns. Provides proper column headers and example data for procurement teams.
   * @tags dbtn/module:cluster_bringup
   * @name download_asset_template
   * @summary Download Asset Template
   * @request GET:/routes/cluster-bringup/download-asset-template
   */
  export namespace download_asset_template {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = DownloadAssetTemplateData;
  }

  /**
   * @description Download the test 3-tier network schematic PNG for testing the cluster bringup workflow. Includes BACKEND_FABRIC, FRONTEND_FABRIC, and OOB_MANAGEMENT tiers with intentional validation issues.
   * @tags dbtn/module:cluster_bringup
   * @name download_test_schematic
   * @summary Download Test Schematic
   * @request GET:/routes/cluster-bringup/download-test-schematic
   */
  export namespace download_test_schematic {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = DownloadTestSchematicData;
  }

  /**
   * @description Download the test 3-tier asset inventory CSV for testing the cluster bringup workflow. Includes network segment, device role, and port information for validation testing.
   * @tags dbtn/module:cluster_bringup
   * @name download_test_csv
   * @summary Download Test Csv
   * @request GET:/routes/cluster-bringup/download-test-csv
   */
  export namespace download_test_csv {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = DownloadTestCsvData;
  }

  /**
   * @description **DHCP Server Webhook Endpoint** Called by the DHCP server (ISC Kea, Infoblox, etc.) when a new device sends a DHCP DISCOVER packet during initial power-on. This is the "gatekeeper" that prevents wrong hardware from getting IPs. **Flow:** 1. DHCP server detects new MAC address 2. Calls this webhook with MAC and optional metadata 3. DHCPScraper verifies hardware identity 4. Returns SUCCESS (with IP) or BLOCKED (no IP assigned) **Security:** - If identity mismatch: Return HTTP 403 Forbidden - DHCP server should NOT assign IP on 403 response - Creates CRITICAL alert for Installation Lead **Integration Example (ISC Kea):** ```json { "hooks-libraries": [{ "library": "/usr/lib/kea/hooks/libdhcp_lease_cmds.so", "parameters": { "on-discover-webhook": "https://yourdomain.riff.works/routes/cluster-bringup/provisioning/discover/PROJECT_ID" } }] } ```
   * @tags dbtn/module:cluster_bringup
   * @name dhcp_discovery_webhook
   * @summary Dhcp Discovery Webhook
   * @request POST:/routes/cluster-bringup/provisioning/discover/{project_id}
   */
  export namespace dhcp_discovery_webhook {
    export type RequestParams = {
      /** Project Id */
      projectId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = DHCPDiscoverRequest;
    export type RequestHeaders = {};
    export type ResponseBody = DhcpDiscoveryWebhookData;
  }

  /**
   * @description **Get Active Provisioning Alerts** Returns all unresolved alerts for the Installation Lead dashboard. Ordered by severity (CRITICAL first) and creation time. **Use Case:** Frontend dashboard polls this endpoint every 5 seconds to show real-time alerts when hardware mismatches are detected. **Alert Types:** - IDENTITY_MISMATCH (CRITICAL): Wrong switch at location - UNKNOWN_DEVICE (MEDIUM): MAC not in Day 0 plan - UNREACHABLE_SWITCH (HIGH): Switch booted but no serial response
   * @tags dbtn/module:cluster_bringup
   * @name get_provisioning_alerts
   * @summary Get Provisioning Alerts
   * @request GET:/routes/cluster-bringup/provisioning/alerts/{project_id}
   */
  export namespace get_provisioning_alerts {
    export type RequestParams = {
      /** Project Id */
      projectId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetProvisioningAlertsData;
  }

  /**
   * @description **Installation Lead Resolves Alert** Three resolution strategies: 1. **SWAP_HARDWARE**: Technician will physically move the switch. - Use when hardware was racked in wrong location - Marks alert as resolved, waits for physical correction 2. **UPDATE_INVENTORY**: Accept detected hardware as correct. - Use when Day 0 inventory was wrong, physical reality is correct - Updates Firestore with actual serial, unblocks device 3. **OVERRIDE_AND_PROCEED**: Proceed despite mismatch (DANGEROUS). - Use only when Installation Lead accepts the risk - ⚠️ Can lead to catastrophic configuration errors - Creates audit trail of override **Audit Trail:** All resolutions are logged with: - Who resolved it (user ID/email) - When it was resolved (timestamp) - Which strategy was used - Resolution outcome
   * @tags dbtn/module:cluster_bringup
   * @name resolve_provisioning_alert
   * @summary Resolve Provisioning Alert
   * @request POST:/routes/cluster-bringup/provisioning/resolve
   */
  export namespace resolve_provisioning_alert {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = ResolveAlertRequest;
    export type RequestHeaders = {};
    export type ResponseBody = ResolveProvisioningAlertData;
  }

  /**
   * @description **Get Real-Time Provisioning Status** Returns overview of all devices and their provisioning state: - PROVISIONED (green): Hardware verified, IP assigned - BLOCKED_IDENTITY_MISMATCH (red): Wrong hardware detected - INVENTORY_UPDATED (yellow): Was corrected via UPDATE_INVENTORY - OVERRIDE_APPLIED (orange): Lead override applied (caution) - PENDING (grey): Waiting for power-on **Use Case:** Dashboard "Rack View" showing color-coded device status.
   * @tags dbtn/module:cluster_bringup
   * @name get_provisioning_status
   * @summary Get Provisioning Status
   * @request GET:/routes/cluster-bringup/provisioning/status/{project_id}
   */
  export namespace get_provisioning_status {
    export type RequestParams = {
      /** Project Id */
      projectId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetProvisioningStatusData;
  }

  /**
   * @description Get health status for a specific tier. Args: projectId: Project identifier tier: Tier name (BACKEND_FABRIC, STORAGE, COMPUTE)
   * @tags dbtn/module:cluster_bringup
   * @name get_tier_health
   * @summary Get Tier Health
   * @request GET:/routes/cluster-bringup/tier-health/{project_id}/{tier}
   */
  export namespace get_tier_health {
    export type RequestParams = {
      /** Project Id */
      projectId: string;
      /** Tier */
      tier: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetTierHealthData;
  }

  /**
   * @description Get overall cluster readiness status with all tiers.
   * @tags dbtn/module:cluster_bringup
   * @name get_cluster_readiness
   * @summary Get Cluster Readiness
   * @request GET:/routes/cluster-bringup/cluster-readiness/{project_id}
   */
  export namespace get_cluster_readiness {
    export type RequestParams = {
      /** Project Id */
      projectId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetClusterReadinessData;
  }

  /**
   * @description Emergency override for tier dependency blocks. Requires CTO-level authorization token. Creates permanent audit trail.
   * @tags dbtn/module:cluster_bringup
   * @name emergency_override
   * @summary Emergency Override
   * @request POST:/routes/cluster-bringup/emergency-override/{project_id}
   */
  export namespace emergency_override {
    export type RequestParams = {
      /** Project Id */
      projectId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = EmergencyOverrideRequest;
    export type RequestHeaders = {};
    export type ResponseBody = EmergencyOverrideData;
  }

  /**
   * @description Get preview of IP allocations before deployment. Shows all planned GPU IP assignments with conflict detection.
   * @tags dbtn/module:cluster_bringup
   * @name get_ip_allocation_preview
   * @summary Get Ip Allocation Preview
   * @request GET:/routes/cluster-bringup/ip-allocation-preview/{project_id}
   */
  export namespace get_ip_allocation_preview {
    export type RequestParams = {
      /** Project Id */
      projectId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetIpAllocationPreviewData;
  }

  /**
   * @description Register a new user using Firebase Admin SDK. This handles both the Firebase Auth account creation and Firestore document creation.
   * @tags dbtn/module:user_registration, dbtn/hasAuth
   * @name register_user
   * @summary Register User
   * @request POST:/routes/register
   */
  export namespace register_user {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = UserRegistrationRequest;
    export type RequestHeaders = {};
    export type ResponseBody = RegisterUserData;
  }

  /**
   * @description List all constraints for the authenticated user with optional filtering. Query Parameters: - domain: Filter by domain (e.g., 'dcdc') - category: Filter by category (e.g., 'safety') - severity: Filter by severity (e.g., 'critical') - active_only: If true, only return active constraints (default: true)
   * @tags dbtn/module:constraints
   * @name list_constraints
   * @summary List Constraints
   * @request GET:/routes/constraints
   */
  export namespace list_constraints {
    export type RequestParams = {};
    export type RequestQuery = {
      /** Domain */
      domain?: string | null;
      /** Category */
      category?: string | null;
      /** Severity */
      severity?: string | null;
      /**
       * Active Only
       * @default true
       */
      active_only?: boolean;
    };
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = ListConstraintsData;
  }

  /**
   * @description Create a new constraint for the authenticated user.
   * @tags dbtn/module:constraints
   * @name create_new_constraint
   * @summary Create New Constraint
   * @request POST:/routes/constraints
   */
  export namespace create_new_constraint {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = ConstraintCreate;
    export type RequestHeaders = {};
    export type ResponseBody = CreateNewConstraintData;
  }

  /**
   * @description Update an existing constraint. Only admins from the same company can update it.
   * @tags dbtn/module:constraints
   * @name update_existing_constraint
   * @summary Update Existing Constraint
   * @request PUT:/routes/constraints/{constraint_id}
   */
  export namespace update_existing_constraint {
    export type RequestParams = {
      /** Constraint Id */
      constraintId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = ConstraintUpdate;
    export type RequestHeaders = {};
    export type ResponseBody = UpdateExistingConstraintData;
  }

  /**
   * @description Delete a constraint. Only admins from the same company can delete it.
   * @tags dbtn/module:constraints
   * @name delete_existing_constraint
   * @summary Delete Existing Constraint
   * @request DELETE:/routes/constraints/{constraint_id}
   */
  export namespace delete_existing_constraint {
    export type RequestParams = {
      /** Constraint Id */
      constraintId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = DeleteExistingConstraintData;
  }

  /**
   * @description Import pre-configured constraint templates for the authenticated user. Requires: company_admin or system_admin role Currently supports 'dcdc' (Data Center Deployment & Commissioning) templates.
   * @tags dbtn/module:constraints
   * @name import_constraint_templates
   * @summary Import Constraint Templates
   * @request POST:/routes/constraints/import-templates
   */
  export namespace import_constraint_templates {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = ImportTemplatesRequest;
    export type RequestHeaders = {};
    export type ResponseBody = ImportConstraintTemplatesData;
  }

  /**
   * @description Get metadata about available constraint template sets.
   * @tags dbtn/module:constraints
   * @name get_available_constraint_templates
   * @summary Get Available Constraint Templates
   * @request GET:/routes/constraints/templates/available
   */
  export namespace get_available_constraint_templates {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetAvailableConstraintTemplatesData;
  }

  /**
   * @description Generates secure, temporary URLs for all media files associated with a specific expert tip.
   * @tags Expert Tips Media, dbtn/module:expert_tips_media, dbtn/hasAuth
   * @name get_secure_media_urls_for_tip
   * @summary Get Secure URLs for an Expert Tip's Media
   * @request GET:/routes/expert-tips-media/{tip_id}
   */
  export namespace get_secure_media_urls_for_tip {
    export type RequestParams = {
      /** Tip Id */
      tipId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetSecureMediaUrlsForTipData;
  }

  /**
   * @description Checks the status of Firebase Admin SDK initialization.
   * @tags dbtn/module:firebase_admin, dbtn/hasAuth
   * @name firebase_status
   * @summary Firebase Status
   * @request GET:/routes/status
   */
  export namespace firebase_status {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = FirebaseStatusData;
  }

  /**
   * @description Retrieve relevant document chunks from knowledge base based on query
   * @tags dbtn/module:knowledge_retrieval, dbtn/hasAuth
   * @name retrieve_knowledge
   * @summary Retrieve Knowledge
   * @request POST:/routes/retrieve-knowledge
   */
  export namespace retrieve_knowledge {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = RetrievalRequest;
    export type RequestHeaders = {};
    export type ResponseBody = RetrieveKnowledgeData;
  }

  /**
   * @description Get the namespace configuration for the authenticated user's company. Returns list of namespaces with their IDs and display names.
   * @tags dbtn/module:knowledge_retrieval, dbtn/hasAuth
   * @name get_company_namespaces_endpoint
   * @summary Get Company Namespaces Endpoint
   * @request GET:/routes/company-namespaces
   */
  export namespace get_company_namespaces_endpoint {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetCompanyNamespacesEndpointData;
  }

  /**
   * @description Trigger topology sync for all nodes in project. This is the main entry point for topology synchronization. It queries Firestore for all COMPUTE nodes and applies topology labels to corresponding Kubernetes nodes. **When to call:** - After new nodes join the cluster - Periodically (every 5 minutes via cron) - After LLDP validation completes - After hardware changes or node replacement - For manual troubleshooting **Example:** ```bash curl -X POST http://localhost:8000/k8s-topology-sync/sync-topology/my-project ``` Args: projectId: Firestore project ID to sync Returns: SyncTopologyResponse with sync results Raises: HTTPException 500: If Firestore client not initialized or sync fails HTTPException 404: If project has no compute nodes
   * @tags dbtn/module:k8s_topology_sync
   * @name sync_topology
   * @summary Sync Topology
   * @request POST:/routes/sync-topology/{project_id}
   */
  export namespace sync_topology {
    export type RequestParams = {
      /** Project Id */
      projectId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = SyncTopologyData;
  }

  /**
   * @description Get topology labels for a specific node. Useful for debugging and validation. Returns the current topology labels applied to a Kubernetes node. **Example:** ```bash curl http://localhost:8000/k8s-topology-sync/node-topology/dgx-su1-r02-s05 ``` Args: node_name: Kubernetes node name Returns: NodeTopologyResponse with topology labels Raises: HTTPException 404: If node not found in Kubernetes HTTPException 500: If kubectl fails
   * @tags dbtn/module:k8s_topology_sync
   * @name get_node_topology
   * @summary Get Node Topology
   * @request GET:/routes/node-topology/{node_name}
   */
  export namespace get_node_topology {
    export type RequestParams = {
      /** Node Name */
      nodeName: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetNodeTopologyData;
  }

  /**
   * @description Verify that all K8s nodes have topology labels. This is a health check endpoint. Use it to ensure topology sync is working correctly. **Health Status:** - HEALTHY: All nodes labeled - DEGRADED: 1-25% unlabeled - CRITICAL: >25% unlabeled **Example:** ```bash curl http://localhost:8000/k8s-topology-sync/verify-sync/my-project ``` Args: projectId: Firestore project ID Returns: VerifySyncResponse with health status
   * @tags dbtn/module:k8s_topology_sync
   * @name verify_sync
   * @summary Verify Sync
   * @request GET:/routes/verify-sync/{project_id}
   */
  export namespace verify_sync {
    export type RequestParams = {
      /** Project Id */
      projectId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = VerifySyncData;
  }

  /**
   * @description Sync topology for a single node (faster than full sync). Useful for: - After node replacement - After hardware changes - After LLDP re-validation - Troubleshooting individual nodes **Example:** ```bash curl -X POST "http://localhost:8000/k8s-topology-sync/sync-single-node/dgx-su1-r02-s05?project_id=my-project" ``` Args: node_name: Node to sync projectId: Firestore project ID (query param) Returns: Dict with sync status
   * @tags dbtn/module:k8s_topology_sync
   * @name sync_single_node
   * @summary Sync Single Node
   * @request POST:/routes/sync-single-node/{node_name}
   */
  export namespace sync_single_node {
    export type RequestParams = {
      /** Node Name */
      nodeName: string;
    };
    export type RequestQuery = {
      /** Project Id */
      projectId: string;
    };
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = SyncSingleNodeData;
  }

  /**
   * @description Synthesizes speech from text using Google Cloud Text-to-Speech, caches it in db.storage, and returns a URL for instant playback.
   * @tags dbtn/module:text_to_speech, dbtn/hasAuth
   * @name synthesize
   * @summary Synthesize
   * @request POST:/routes/synthesize
   */
  export namespace synthesize {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = SynthesisRequest;
    export type RequestHeaders = {};
    export type ResponseBody = SynthesizeData;
  }

  /**
   * @description This is the main entry point for the document processing worker. It's triggered by an HTTP request (e.g., from a Cloud Task or another service).
   * @tags dbtn/module:doc_processor
   * @name process_document_worker
   * @summary Process Document Worker
   * @request POST:/routes/process-document-worker
   */
  export namespace process_document_worker {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = WorkerPayload;
    export type RequestHeaders = {};
    export type ResponseBody = ProcessDocumentWorkerData;
  }

  /**
   * @description Parse and validate a Bill of Materials file (CSV or Excel).
   * @tags onboarding, dbtn/module:onboarding
   * @name validate_bom_upload
   * @summary Validate Bom Upload
   * @request POST:/routes/onboarding/validate-bom
   */
  export namespace validate_bom_upload {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = BodyValidateBomUpload;
    export type RequestHeaders = {};
    export type ResponseBody = ValidateBomUploadData;
  }

  /**
   * @description Return all available deployment templates.
   * @tags onboarding, dbtn/module:onboarding
   * @name list_deployment_templates
   * @summary List Deployment Templates
   * @request GET:/routes/onboarding/templates
   */
  export namespace list_deployment_templates {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = ListDeploymentTemplatesData;
  }

  /**
   * @description Generate ZTP config bundle and return as downloadable ZIP. Builds switch configs, DHCP config, cabling matrix, and setup guide based on the user's topology configuration and returns as ZIP bytes.
   * @tags onboarding, dbtn/module:onboarding
   * @name generate_onboarding_configs
   * @summary Generate Onboarding Configs
   * @request POST:/routes/onboarding/generate-configs
   */
  export namespace generate_onboarding_configs {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = GenerateConfigRequest;
    export type RequestHeaders = {};
    export type ResponseBody = GenerateOnboardingConfigsData;
  }

  /**
   * @description Get pending user requests for approval
   * @tags dbtn/module:user_management, dbtn/hasAuth
   * @name get_pending_users
   * @summary Get Pending Users
   * @request GET:/routes/admin/pending-users
   */
  export namespace get_pending_users {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetPendingUsersData;
  }

  /**
   * @description Approve or reject a user request
   * @tags dbtn/module:user_management, dbtn/hasAuth
   * @name approve_reject_user
   * @summary Approve Reject User
   * @request POST:/routes/admin/approve-user
   */
  export namespace approve_reject_user {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = ApproveRejectRequest;
    export type RequestHeaders = {};
    export type ResponseBody = ApproveRejectUserData;
  }

  /**
   * @description Get list of available domains for assignment
   * @tags dbtn/module:user_management, dbtn/hasAuth
   * @name get_available_domains
   * @summary Get Available Domains
   * @request GET:/routes/admin/domains
   */
  export namespace get_available_domains {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetAvailableDomainsData;
  }

  /**
   * @description Assign a specific domain to a user (Company Admin only)
   * @tags dbtn/module:user_management, dbtn/hasAuth
   * @name assign_user_domain
   * @summary Assign User Domain
   * @request POST:/routes/admin/assign-domain
   */
  export namespace assign_user_domain {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = AssignDomainRequest;
    export type RequestHeaders = {};
    export type ResponseBody = AssignUserDomainData;
  }

  /**
   * @description Get all users in the system
   * @tags dbtn/module:user_management, dbtn/hasAuth
   * @name get_all_users
   * @summary Get All Users
   * @request GET:/routes/admin/users
   */
  export namespace get_all_users {
    export type RequestParams = {};
    export type RequestQuery = {
      /**
       * Approval Status List Str
       * Comma-separated list of approval statuses to filter by (e.g., 'approved' or 'rejected')
       */
      approval_status_list_str?: string | null;
    };
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetAllUsersData;
  }

  /**
   * @description Handles the creation of the expert tip database entry. This endpoint assumes media files have already been uploaded to GCS and their URLs are provided in the request.
   * @tags Expert Tips, dbtn/module:expert_tips, dbtn/hasAuth
   * @name create_expert_tip_entry
   * @summary Creates an expert tip entry in Firestore after files are uploaded
   * @request POST:/routes/expert-tips/create-entry
   */
  export namespace create_expert_tip_entry {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = CreateExpertTipEntryRequest;
    export type RequestHeaders = {};
    export type ResponseBody = CreateExpertTipEntryData;
  }

  /**
   * @description Create a new customer account. This is the entry point for new customer signups. Creates isolated namespace in Firestore and sets up admin user. **Example:** ```bash curl -X POST http://localhost:8000/customer-management/customers       -H "Content-Type: application/json"       -d '{ "company_name": "NVIDIA Corporation", "admin_email": "admin@nvidia.com", "license_tier": "enterprise", "metadata": {"industry": "AI", "employee_count": 10000} }' ``` Args: request: CreateCustomerRequest Returns: CustomerResponse with customer_id Raises: HTTPException 400: If license_tier invalid or customer exists HTTPException 500: If CustomerManager not initialized
   * @tags dbtn/module:customer_management
   * @name create_customer
   * @summary Create Customer
   * @request POST:/routes/customers
   */
  export namespace create_customer {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = CreateCustomerRequest;
    export type RequestHeaders = {};
    export type ResponseBody = CreateCustomerData;
  }

  /**
   * @description List all customers. **Security:** Platform admin only. This endpoint is for internal operations team, not customer-facing. Args: status: Filter by status ("active", "trial", "suspended") license_tier: Filter by tier ("starter", "professional", "enterprise") limit: Max results (default 100) x_platform_admin: Admin auth token Returns: List of CustomerResponse Raises: HTTPException 403: If not platform admin
   * @tags dbtn/module:customer_management
   * @name list_customers
   * @summary List Customers
   * @request GET:/routes/customers
   */
  export namespace list_customers {
    export type RequestParams = {};
    export type RequestQuery = {
      /** Status */
      status?: string | null;
      /** License Tier */
      license_tier?: string | null;
      /**
       * Limit
       * @default 100
       */
      limit?: number;
    };
    export type RequestBody = never;
    export type RequestHeaders = {
      /** X-Platform-Admin */
      "x-platform-admin"?: string | null;
    };
    export type ResponseBody = ListCustomersData;
  }

  /**
   * @description Get customer details by ID. **Security:** Users can only access their own customer data. Platform admins can access any customer. Args: customer_id: Customer ID x_customer_id: Customer ID from header (for auth check) Returns: CustomerResponse Raises: HTTPException 403: If trying to access another customer's data HTTPException 404: If customer not found
   * @tags dbtn/module:customer_management
   * @name get_customer
   * @summary Get Customer
   * @request GET:/routes/customers/{customer_id}
   */
  export namespace get_customer {
    export type RequestParams = {
      /** Customer Id */
      customerId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {
      /** X-Customer-Id */
      "x-customer-id"?: string | null;
    };
    export type ResponseBody = GetCustomerData;
  }

  /**
   * @description Update customer data. **Allowed updates:** - company_name (if legal name changes) - metadata (industry, employee_count, etc.) - status (admin only - use suspend/activate endpoints instead) Args: customer_id: Customer ID request: UpdateCustomerRequest x_customer_id: Customer ID from header (for auth check) Returns: Updated CustomerResponse Raises: HTTPException 403: If unauthorized HTTPException 404: If customer not found
   * @tags dbtn/module:customer_management
   * @name update_customer
   * @summary Update Customer
   * @request PUT:/routes/customers/{customer_id}
   */
  export namespace update_customer {
    export type RequestParams = {
      /** Customer Id */
      customerId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = UpdateCustomerRequest;
    export type RequestHeaders = {
      /** X-Customer-Id */
      "x-customer-id"?: string | null;
    };
    export type ResponseBody = UpdateCustomerData;
  }

  /**
   * @description Delete a customer and ALL their data. ⚠️ **IRREVERSIBLE OPERATION** **Platform admin only.** Deletes: - Customer account - All infrastructure data - All projects - All users - All audit logs Use case: Customer requests data deletion (GDPR right to be forgotten). Args: customer_id: Customer ID confirm: Must be True to actually delete x_platform_admin: Admin auth token Returns: Success message Raises: HTTPException 403: If not platform admin HTTPException 400: If confirm not True
   * @tags dbtn/module:customer_management
   * @name delete_customer
   * @summary Delete Customer
   * @request DELETE:/routes/customers/{customer_id}
   */
  export namespace delete_customer {
    export type RequestParams = {
      /** Customer Id */
      customerId: string;
    };
    export type RequestQuery = {
      /**
       * Confirm
       * @default false
       */
      confirm?: boolean;
    };
    export type RequestBody = never;
    export type RequestHeaders = {
      /** X-Platform-Admin */
      "x-platform-admin"?: string | null;
    };
    export type ResponseBody = DeleteCustomerData;
  }

  /**
   * @description Upgrade customer's license tier. **Upgrade paths:** - starter → professional - starter → enterprise - professional → enterprise Downgrades are not allowed (contact support for special cases). Args: customer_id: Customer ID request: UpgradeLicenseRequest x_customer_id: Customer ID from header (for auth check) Returns: Updated CustomerResponse Raises: HTTPException 400: If downgrade attempted or invalid tier HTTPException 403: If unauthorized
   * @tags dbtn/module:customer_management
   * @name upgrade_license
   * @summary Upgrade License
   * @request POST:/routes/customers/{customer_id}/upgrade
   */
  export namespace upgrade_license {
    export type RequestParams = {
      /** Customer Id */
      customerId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = UpgradeLicenseRequest;
    export type RequestHeaders = {
      /** X-Customer-Id */
      "x-customer-id"?: string | null;
    };
    export type ResponseBody = UpgradeLicenseData;
  }

  /**
   * @description Suspend a customer account. **Platform admin only.** Suspended customers: - Cannot log in - Cannot access any features - Data is retained (not deleted) - Can be reactivated Common reasons: Payment failure, policy violation, security breach. Args: customer_id: Customer ID request: SuspendCustomerRequest x_platform_admin: Admin auth token Returns: Success message Raises: HTTPException 403: If not platform admin
   * @tags dbtn/module:customer_management
   * @name suspend_customer
   * @summary Suspend Customer
   * @request POST:/routes/customers/{customer_id}/suspend
   */
  export namespace suspend_customer {
    export type RequestParams = {
      /** Customer Id */
      customerId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = SuspendCustomerRequest;
    export type RequestHeaders = {
      /** X-Platform-Admin */
      "x-platform-admin"?: string | null;
    };
    export type ResponseBody = SuspendCustomerData;
  }

  /**
   * @description Activate a suspended customer. **Platform admin only.** Args: customer_id: Customer ID x_platform_admin: Admin auth token Returns: Success message Raises: HTTPException 403: If not platform admin
   * @tags dbtn/module:customer_management
   * @name activate_customer
   * @summary Activate Customer
   * @request POST:/routes/customers/{customer_id}/activate
   */
  export namespace activate_customer {
    export type RequestParams = {
      /** Customer Id */
      customerId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {
      /** X-Platform-Admin */
      "x-platform-admin"?: string | null;
    };
    export type ResponseBody = ActivateCustomerData;
  }

  /**
   * @description Check GPU quota usage for customer. Returns current GPU count vs license limit. Used to enforce quota and prompt upgrades. Args: customer_id: Customer ID x_customer_id: Customer ID from header (for auth check) Returns: QuotaResponse Raises: HTTPException 403: If unauthorized HTTPException 404: If customer not found
   * @tags dbtn/module:customer_management
   * @name check_quota
   * @summary Check Quota
   * @request GET:/routes/customers/{customer_id}/quota
   */
  export namespace check_quota {
    export type RequestParams = {
      /** Customer Id */
      customerId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {
      /** X-Customer-Id */
      "x-customer-id"?: string | null;
    };
    export type ResponseBody = CheckQuotaData;
  }

  /**
   * @description Deploy K3s control plane on admin node. This is a ONE-TIME operation to initialize the cluster. Subsequent nodes join via /join-node. **Usage:** ``` POST /kubernetes/bootstrap { "control_plane_ip": "10.0.0.10" } ```
   * @tags dbtn/module:kubernetes
   * @name bootstrap_control_plane_endpoint
   * @summary Bootstrap Control Plane Endpoint
   * @request POST:/routes/kubernetes/bootstrap
   */
  export namespace bootstrap_control_plane_endpoint {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = BootstrapRequest;
    export type RequestHeaders = {};
    export type ResponseBody = BootstrapControlPlaneEndpointData;
  }

  /**
   * @description Add worker node to K8s cluster after ZTP provisioning. Called by DHCPScraper after OS installation completes. Only COMPUTE tier nodes join the cluster. **Usage:** ``` POST /kubernetes/join-node { "node_ip": "10.244.1.5", "node_hostname": "SU1-RACK01-SRV01", "tier": "COMPUTE", "gpu_count": 8 } ```
   * @tags dbtn/module:kubernetes
   * @name join_worker_node
   * @summary Join Worker Node
   * @request POST:/routes/kubernetes/join-node
   */
  export namespace join_worker_node {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = JoinNodeRequest;
    export type RequestHeaders = {};
    export type ResponseBody = JoinWorkerNodeData;
  }

  /**
   * @description List all K8s nodes with GPU inventory. Returns detailed info for each node including: - GPU count (from nvidia.com/gpu resource) - Node status (Ready/NotReady) - Tier label (COMPUTE/STORAGE/ADMIN) - Provisioning source (dhcp-scraper, manual, etc.) **Usage:** ``` GET /kubernetes/nodes ```
   * @tags dbtn/module:kubernetes
   * @name list_cluster_nodes
   * @summary List Cluster Nodes
   * @request GET:/routes/kubernetes/nodes
   */
  export namespace list_cluster_nodes {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = ListClusterNodesData;
  }

  /**
   * @description Get cluster health metrics. Returns: - Total/Ready node counts - Total GPU count across cluster - Control plane IP **Usage:** ``` GET /kubernetes/cluster-status ```
   * @tags dbtn/module:kubernetes
   * @name get_cluster_status
   * @summary Get Cluster Status
   * @request GET:/routes/kubernetes/cluster-status
   */
  export namespace get_cluster_status {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetClusterStatusData;
  }

  /**
   * @description Get detailed info for a specific node. Args: node_name: K8s node name (e.g., SU1-RACK01-SRV01) **Usage:** ``` GET /kubernetes/node/SU1-RACK01-SRV01 ```
   * @tags dbtn/module:kubernetes
   * @name get_node_details
   * @summary Get Node Details
   * @request GET:/routes/kubernetes/node/{node_name}
   */
  export namespace get_node_details {
    export type RequestParams = {
      /** Node Name */
      nodeName: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetNodeDetailsData;
  }

  /**
   * @description Handle ZTP completion webhook and trigger K8s worker join. Called by switches/nodes after ZTP script execution completes. For COMPUTE tier nodes, this triggers automatic K8s cluster join. **Workflow:** 1. ZTP script completes OS installation 2. Node sends POST /kubernetes/ztp-complete 3. Lookup node in Firestore (check k8s_join_pending flag) 4. If COMPUTE node → trigger K8s join via K8sProvisioner 5. Return status **Usage:** ``` POST /kubernetes/ztp-complete { "node_hostname": "SU1-RACK01-SRV01", "node_ip": "10.244.1.5", "mac_address": "00:1A:2B:3C:4D:5E", "ztp_status": "SUCCESS" } ```
   * @tags dbtn/module:kubernetes
   * @name handle_ztp_completion
   * @summary Handle Ztp Completion
   * @request POST:/routes/kubernetes/ztp-complete
   */
  export namespace handle_ztp_completion {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = ZTPCompletionRequest;
    export type RequestHeaders = {};
    export type ResponseBody = HandleZtpCompletionData;
  }

  /**
   * No description
   * @tags dbtn/module:technician_uploads, dbtn/hasAuth
   * @name upload_technician_file_v2
   * @summary Upload Technician File V2
   * @request POST:/routes/technician_uploads/upload_file
   */
  export namespace upload_technician_file_v2 {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = BodyUploadTechnicianFileV2;
    export type RequestHeaders = {};
    export type ResponseBody = UploadTechnicianFileV2Data;
  }

  /**
   * @description Takes a session_id, fetches the full session context from Firestore, and then uses Google Gemini to generate a professional report draft.
   * @tags technicianreport, dbtn/module:technicianreport, dbtn/hasAuth
   * @name generate_llm_draft_report
   * @summary Generate Llm Draft Report
   * @request POST:/routes/technicianreport/generate
   */
  export namespace generate_llm_draft_report {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = ReportGenerationRequest;
    export type RequestHeaders = {};
    export type ResponseBody = GenerateLlmDraftReportData;
  }

  /**
   * @description Saves the final report. It now fetches the 'assignmentLocation' from the original troubleshooting session instead of receiving coordinates.
   * @tags technicianreport, dbtn/module:technicianreport, dbtn/hasAuth
   * @name save_finalized_report
   * @summary Save Finalized Report
   * @request POST:/routes/technicianreport/save
   */
  export namespace save_finalized_report {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = ReportSaveRequest;
    export type RequestHeaders = {};
    export type ResponseBody = SaveFinalizedReportData;
  }

  /**
   * @description Retrieves all troubleshooting reports filed by the currently authenticated technician, ordered from newest to oldest.
   * @tags technicianreport, dbtn/module:technicianreport, dbtn/hasAuth
   * @name get_my_reports
   * @summary Get My Reports
   * @request GET:/routes/technicianreport/my-reports
   */
  export namespace get_my_reports {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetMyReportsData;
  }

  /**
   * @description Retrieves a single troubleshooting report by its document ID from Firestore.
   * @tags technicianreport, dbtn/module:technicianreport, dbtn/hasAuth
   * @name get_specific_report
   * @summary Get Specific Report
   * @request GET:/routes/technicianreport/{report_id}
   */
  export namespace get_specific_report {
    export type RequestParams = {
      /** Report Id */
      reportId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetSpecificReportData;
  }

  /**
   * @description Creates a user account with proper hierarchical approval workflow: - System Admins are auto-approved - Company Admins require System Admin approval - Technicians require Company Admin approval
   * @tags dbtn/module:direct_user_approval, dbtn/hasAuth
   * @name direct_approve_user2
   * @summary Direct Approve User2
   * @request POST:/routes/direct-approve-user2
   */
  export namespace direct_approve_user2 {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = DirectRegistrationRequest;
    export type RequestHeaders = {};
    export type ResponseBody = DirectApproveUser2Data;
  }

  /**
   * @description Directly approve or reject a user without needing the admin UI
   * @tags dbtn/module:approve_user_script, dbtn/hasAuth
   * @name direct_approve_user
   * @summary Direct Approve User
   * @request POST:/routes/direct-approve
   */
  export namespace direct_approve_user {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = DirectApproveRequest;
    export type RequestHeaders = {};
    export type ResponseBody = DirectApproveUserData;
  }

  /**
   * @description Uploads a document, saves it to GCS, and enqueues a processing task.
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name upload_document
   * @summary Upload Document
   * @request POST:/routes/upload-document
   */
  export namespace upload_document {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = BodyUploadDocument;
    export type RequestHeaders = {};
    export type ResponseBody = UploadDocumentData;
  }

  /**
   * No description
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name get_document_status
   * @summary Get Document Status
   * @request GET:/routes/documents/{doc_id}/status
   */
  export namespace get_document_status {
    export type RequestParams = {
      /** Doc Id */
      docId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetDocumentStatusData;
  }

  /**
   * @description List documents (admin only)
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name list_documents
   * @summary List Documents
   * @request GET:/routes/documents
   */
  export namespace list_documents {
    export type RequestParams = {};
    export type RequestQuery = {
      /** Company */
      company?: string | null;
      /** Organization */
      organization?: string | null;
      /** Status */
      status?: string | null;
      /** Search */
      search?: string | null;
      /** Jobid */
      jobId?: string | null;
      /**
       * Limit
       * @default 50
       */
      limit?: number;
      /**
       * Offset
       * @default 0
       */
      offset?: number;
    };
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = ListDocumentsData;
  }

  /**
   * @description Provides a document count summary for a company admin.
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name get_document_metrics_summary
   * @summary Get Document Metrics Summary
   * @request GET:/routes/document-metrics-summary
   */
  export namespace get_document_metrics_summary {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetDocumentMetricsSummaryData;
  }

  /**
   * @description Optimized version of get_document. Uses a global Firestore client to avoid re-initialization and disk I/O on every call.
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name get_document_optimal
   * @summary Get Document Optimal
   * @request GET:/routes/documents/{doc_id}/get_document_optimal
   */
  export namespace get_document_optimal {
    export type RequestParams = {
      /** Doc Id */
      docId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetDocumentOptimalData;
  }

  /**
   * No description
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name get_document
   * @summary Get Document
   * @request GET:/routes/documents/{doc_id}
   */
  export namespace get_document {
    export type RequestParams = {
      /** Doc Id */
      docId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetDocumentData;
  }

  /**
   * @description Deletes a document and its associated data from Firestore, GCS, and Pinecone. This is a permanent action.
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name delete_document
   * @summary Delete Document
   * @request DELETE:/routes/documents/{doc_id}
   */
  export namespace delete_document {
    export type RequestParams = {
      /** Doc Id */
      docId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = DeleteDocumentData;
  }

  /**
   * @description Generates a secure, short-lived URL to view a document.
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name get_secure_document_url
   * @summary Get Secure Document Url
   * @request GET:/routes/get-secure-document-url/{document_id}
   */
  export namespace get_secure_document_url {
    export type RequestParams = {
      /** Document Id */
      documentId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetSecureDocumentUrlData;
  }

  /**
   * @description Update document metadata (admin only)
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name update_document
   * @summary Update Document
   * @request PUT:/routes/documents/{document_id}
   */
  export namespace update_document {
    export type RequestParams = {
      /** Document Id */
      documentId: string;
    };
    export type RequestQuery = {};
    export type RequestBody = DocumentUpdateRequest;
    export type RequestHeaders = {};
    export type ResponseBody = UpdateDocumentData;
  }

  /**
   * @description Get admin dashboard metrics
   * @tags dbtn/module:admin, dbtn/hasAuth
   * @name get_admin_metrics
   * @summary Get Admin Metrics
   * @request GET:/routes/admin/metrics
   */
  export namespace get_admin_metrics {
    export type RequestParams = {};
    export type RequestQuery = {
      /**
       * Company
       * Filter metrics by company
       */
      company?: string | null;
    };
    export type RequestBody = never;
    export type RequestHeaders = {};
    export type ResponseBody = GetAdminMetricsData;
  }

  /**
   * @description Dummy endpoint to reprocess a document that might be stuck. In a real scenario, this would trigger a background task.
   * @tags dbtn/module:admin, dbtn/hasAuth
   * @name reprocess_stuck_document
   * @summary Reprocess Stuck Document
   * @request POST:/routes/admin/reprocess_document
   */
  export namespace reprocess_stuck_document {
    export type RequestParams = {};
    export type RequestQuery = {};
    export type RequestBody = ReprocessRequest;
    export type RequestHeaders = {};
    export type ResponseBody = ReprocessStuckDocumentData;
  }
}
