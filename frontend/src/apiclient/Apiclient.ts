import {
  ActivateCustomerData,
  ActivateCustomerError,
  ActivateCustomerParams,
  AddExpertEntryToKnowledgeBaseData,
  AddExpertEntryToKnowledgeBaseError,
  AddSessionRequest,
  AddSessionToKnowledgeBaseData,
  AddSessionToKnowledgeBaseError,
  ApproveExpertTipData,
  ApproveExpertTipError,
  ApproveRejectRequest,
  ApproveRejectUserData,
  ApproveRejectUserError,
  AssignDomainRequest,
  AssignUserDomainData,
  AssignUserDomainError,
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
  BootstrapControlPlaneEndpointError,
  BootstrapRequest,
  BulkDeleteHistoricRecordsData,
  BulkDeleteHistoricRecordsError,
  BulkDeleteHistoricRecordsRequest,
  CablingValidationRequest,
  CheckHealthData,
  CheckQuotaData,
  CheckQuotaError,
  CheckQuotaParams,
  ConfigureSchematicProcessingData,
  ConfigureSchematicProcessingError,
  ConstraintCreate,
  ConstraintUpdate,
  CreateCustomerData,
  CreateCustomerError,
  CreateCustomerRequest,
  CreateExpertTipEntryData,
  CreateExpertTipEntryError,
  CreateExpertTipEntryRequest,
  CreateNewConstraintData,
  CreateNewConstraintError,
  DHCPDiscoverRequest,
  DeleteCustomerData,
  DeleteCustomerError,
  DeleteCustomerParams,
  DeleteDocumentData,
  DeleteDocumentError,
  DeleteDocumentParams,
  DeleteExistingConstraintData,
  DeleteExistingConstraintError,
  DeleteExistingConstraintParams,
  DeleteExpertTipFromKnowledgeBaseData,
  DeleteExpertTipFromKnowledgeBaseError,
  DeleteHistoricRecordData,
  DeleteHistoricRecordError,
  DeleteHistoricRecordParams,
  DeleteProjectData,
  DeleteProjectError,
  DeleteProjectParams,
  DeleteSessionFromKnowledgeBaseData,
  DeleteSessionFromKnowledgeBaseError,
  DeleteSessionRequest,
  DhcpDiscoveryWebhookData,
  DhcpDiscoveryWebhookError,
  DhcpDiscoveryWebhookParams,
  DirectApproveRequest,
  DirectApproveUser2Data,
  DirectApproveUser2Error,
  DirectApproveUserData,
  DirectApproveUserError,
  DirectRegistrationRequest,
  DiscoveryReport,
  DocumentUpdateRequest,
  DownloadAssetTemplateData,
  DownloadTestCsvData,
  DownloadTestSchematicData,
  EmailRequest,
  EmergencyOverrideData,
  EmergencyOverrideError,
  EmergencyOverrideParams,
  EmergencyOverrideRequest,
  ExpertKnowledgeRequest,
  ExpertTipRequest,
  ExportCablingMatrixData,
  ExportCablingMatrixError,
  ExportCablingMatrixParams,
  FeedbackTranscriptionRequest,
  FirebaseStatusData,
  GenerateConfigRequest,
  GenerateLlmDraftReportData,
  GenerateLlmDraftReportError,
  GenerateOnboardingConfigsData,
  GenerateOnboardingConfigsError,
  GenerateResponseData,
  GenerateResponseError,
  GetAdminMetricsData,
  GetAdminMetricsError,
  GetAdminMetricsParams,
  GetAllUsersData,
  GetAllUsersError,
  GetAllUsersParams,
  GetAvailableConstraintTemplatesData,
  GetAvailableDomainsData,
  GetClusterReadinessData,
  GetClusterReadinessError,
  GetClusterReadinessParams,
  GetClusterStatusData,
  GetCompanyNamespacesEndpointData,
  GetCsvHeadersData,
  GetCsvHeadersError,
  GetCustomerData,
  GetCustomerError,
  GetCustomerParams,
  GetDiscoveryScriptData,
  GetDiscoveryScriptError,
  GetDiscoveryScriptParams,
  GetDocumentData,
  GetDocumentError,
  GetDocumentMetricsSummaryData,
  GetDocumentOptimalData,
  GetDocumentOptimalError,
  GetDocumentOptimalParams,
  GetDocumentParams,
  GetDocumentStatusData,
  GetDocumentStatusError,
  GetDocumentStatusParams,
  GetExtractionResultsData,
  GetExtractionResultsError,
  GetExtractionResultsParams,
  GetFullZtpConfigData,
  GetFullZtpConfigError,
  GetFullZtpConfigParams,
  GetIpAllocationPreviewData,
  GetIpAllocationPreviewError,
  GetIpAllocationPreviewParams,
  GetMergeValidationData,
  GetMergeValidationError,
  GetMergeValidationParams,
  GetMyReportsData,
  GetNodeDetailsData,
  GetNodeDetailsError,
  GetNodeDetailsParams,
  GetNodeTopologyData,
  GetNodeTopologyError,
  GetNodeTopologyParams,
  GetPendingUsersData,
  GetProcessingStatusData,
  GetProcessingStatusError,
  GetProcessingStatusParams,
  GetProvisioningAlertsData,
  GetProvisioningAlertsError,
  GetProvisioningAlertsParams,
  GetProvisioningStatusData,
  GetProvisioningStatusError,
  GetProvisioningStatusParams,
  GetSecureDocumentUrlData,
  GetSecureDocumentUrlError,
  GetSecureDocumentUrlParams,
  GetSecureMediaUrlsForTipData,
  GetSecureMediaUrlsForTipError,
  GetSecureMediaUrlsForTipParams,
  GetSpecificReportData,
  GetSpecificReportError,
  GetSpecificReportParams,
  GetTierHealthData,
  GetTierHealthError,
  GetTierHealthParams,
  HandleDiscoveryCallbackData,
  HandleDiscoveryCallbackError,
  HandleZtpCompletionData,
  HandleZtpCompletionError,
  ImportConstraintTemplatesData,
  ImportConstraintTemplatesError,
  ImportTemplatesRequest,
  JoinNodeRequest,
  JoinWorkerNodeData,
  JoinWorkerNodeError,
  ListClusterNodesData,
  ListConstraintsData,
  ListConstraintsError,
  ListConstraintsParams,
  ListCustomersData,
  ListCustomersError,
  ListCustomersParams,
  ListDeploymentTemplatesData,
  ListDocumentsData,
  ListDocumentsError,
  ListDocumentsParams,
  ListHistoricRecordsData,
  ListHistoricRecordsError,
  ListHistoricRecordsParams,
  ListProjectsData,
  ProcessDocumentWorkerData,
  ProcessDocumentWorkerError,
  RegisterUserData,
  RegisterUserError,
  RejectExpertTipData,
  RejectExpertTipError,
  ReportGenerationRequest,
  ReportSaveRequest,
  ReprocessRequest,
  ReprocessStuckDocumentData,
  ReprocessStuckDocumentError,
  ResolveAlertRequest,
  ResolveProvisioningAlertData,
  ResolveProvisioningAlertError,
  ResponseRequest,
  RetrievalRequest,
  RetrieveKnowledgeData,
  RetrieveKnowledgeError,
  SaveFinalizedReportData,
  SaveFinalizedReportError,
  SchematicConfigRequest,
  SearchWebData,
  SearchWebError,
  SendEmailData,
  SendEmailError,
  StreamAudioFileData,
  StreamAudioFileError,
  StreamAudioFileParams,
  SuspendCustomerData,
  SuspendCustomerError,
  SuspendCustomerParams,
  SuspendCustomerRequest,
  SyncSingleNodeData,
  SyncSingleNodeError,
  SyncSingleNodeParams,
  SyncTopologyData,
  SyncTopologyError,
  SyncTopologyParams,
  SynthesisRequest,
  SynthesizeData,
  SynthesizeError,
  TranscribeAudioData,
  TranscribeAudioError,
  TranscribeAudioOptionsData,
  TranscribeFeedbackData,
  TranscribeFeedbackError,
  UpdateCustomerData,
  UpdateCustomerError,
  UpdateCustomerParams,
  UpdateCustomerRequest,
  UpdateDocumentData,
  UpdateDocumentError,
  UpdateDocumentParams,
  UpdateExistingConstraintData,
  UpdateExistingConstraintError,
  UpdateExistingConstraintParams,
  UpgradeLicenseData,
  UpgradeLicenseError,
  UpgradeLicenseParams,
  UpgradeLicenseRequest,
  UploadAssetInventoryData,
  UploadAssetInventoryError,
  UploadAssetInventoryParams,
  UploadDocumentData,
  UploadDocumentError,
  UploadGeneralFileData,
  UploadGeneralFileError,
  UploadHistoricRecordsCsvData,
  UploadHistoricRecordsCsvError,
  UploadSchematicFileData,
  UploadSchematicFileError,
  UploadTechnicianFileV2Data,
  UploadTechnicianFileV2Error,
  UploadZipArchiveData,
  UploadZipArchiveError,
  UserRegistrationRequest,
  ValidateBomUploadData,
  ValidateBomUploadError,
  ValidateCablingData,
  ValidateCablingError,
  VerifySyncData,
  VerifySyncError,
  VerifySyncParams,
  WebSearchRequest,
  WorkerPayload,
  ZTPCompletionRequest,
} from "./data-contracts";
import { ContentType, HttpClient, RequestParams } from "./http-client";

export class Apiclient<SecurityDataType = unknown> extends HttpClient<SecurityDataType> {
  /**
   * @description Check health of application. Returns 200 when OK, 500 when not.
   *
   * @name check_health
   * @summary Check Health
   * @request GET:/_healthz
   */
  check_health = (params: RequestParams = {}) =>
    this.request<CheckHealthData, any>({
      path: `/_healthz`,
      method: "GET",
      ...params,
    });

  /**
   * @description Adds a specific user session's Q&A to the knowledge base.
   *
   * @tags knowledge_base, dbtn/module:knowledge_base, dbtn/hasAuth
   * @name add_session_to_knowledge_base
   * @summary Add Session To Knowledge Base
   * @request POST:/routes/add-session-to-knowledge-base
   */
  add_session_to_knowledge_base = (data: AddSessionRequest, params: RequestParams = {}) =>
    this.request<AddSessionToKnowledgeBaseData, AddSessionToKnowledgeBaseError>({
      path: `/routes/add-session-to-knowledge-base`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * No description
   *
   * @tags dbtn/module:knowledge_base, dbtn/hasAuth
   * @name add_expert_entry_to_knowledge_base
   * @summary Add Expert Entry To Knowledge Base
   * @request POST:/routes/add-expert-entry-to-knowledge-base
   */
  add_expert_entry_to_knowledge_base = (data: ExpertKnowledgeRequest, params: RequestParams = {}) =>
    this.request<AddExpertEntryToKnowledgeBaseData, AddExpertEntryToKnowledgeBaseError>({
      path: `/routes/add-expert-entry-to-knowledge-base`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Deletes a session's vector from Pinecone and updates Firestore.
   *
   * @tags dbtn/module:knowledge_base, dbtn/hasAuth
   * @name delete_session_from_knowledge_base
   * @summary Delete Session From Knowledge Base
   * @request DELETE:/routes/delete-session-from-knowledge-base
   */
  delete_session_from_knowledge_base = (data: DeleteSessionRequest, params: RequestParams = {}) =>
    this.request<DeleteSessionFromKnowledgeBaseData, DeleteSessionFromKnowledgeBaseError>({
      path: `/routes/delete-session-from-knowledge-base`,
      method: "DELETE",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Approves an expert tip, processes its content and media, generates an embedding, and adds it to the company's Pinecone knowledge base.
   *
   * @tags knowledge_base, expert_tips, dbtn/module:knowledge_base, dbtn/hasAuth
   * @name approve_expert_tip
   * @summary Approve Expert Tip
   * @request POST:/routes/approve_expert_tip
   */
  approve_expert_tip = (data: ExpertTipRequest, params: RequestParams = {}) =>
    this.request<ApproveExpertTipData, ApproveExpertTipError>({
      path: `/routes/approve_expert_tip`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Rejects an expert tip. If it was previously approved and added to the knowledge base, removes it from Pinecone before updating the status to 'rejected'.
   *
   * @tags knowledge_base, expert_tips, dbtn/module:knowledge_base, dbtn/hasAuth
   * @name reject_expert_tip
   * @summary Reject Expert Tip
   * @request POST:/routes/reject_expert_tip
   */
  reject_expert_tip = (data: ExpertTipRequest, params: RequestParams = {}) =>
    this.request<RejectExpertTipData, RejectExpertTipError>({
      path: `/routes/reject_expert_tip`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Deletes an approved expert tip from the Pinecone knowledge base and updates its status in Firestore to 'deleted'.
   *
   * @tags knowledge_base, expert_tips, dbtn/module:knowledge_base, dbtn/hasAuth
   * @name delete_expert_tip_from_knowledge_base
   * @summary Delete Expert Tip From Knowledge Base
   * @request POST:/routes/delete_expert_tip_from_knowledge_base
   */
  delete_expert_tip_from_knowledge_base = (data: ExpertTipRequest, params: RequestParams = {}) =>
    this.request<DeleteExpertTipFromKnowledgeBaseData, DeleteExpertTipFromKnowledgeBaseError>({
      path: `/routes/delete_expert_tip_from_knowledge_base`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Streams an audio file stored in db.storage.binary.
   *
   * @tags stream, dbtn/module:audio_files, dbtn/hasAuth
   * @name stream_audio_file
   * @summary Stream Audio File
   * @request GET:/routes/audio_files/stream/{filename}
   */
  stream_audio_file = ({ filename, ...query }: StreamAudioFileParams, params: RequestParams = {}) =>
    this.requestStream<StreamAudioFileData, StreamAudioFileError>({
      path: `/routes/audio_files/stream/${filename}`,
      method: "GET",
      ...params,
    });

  /**
   * No description
   *
   * @tags dbtn/module:transcription, dbtn/hasAuth
   * @name transcribe_audio
   * @summary Transcribe Audio
   * @request POST:/routes/transcribe-audio
   */
  transcribe_audio = (data: BodyTranscribeAudio, params: RequestParams = {}) =>
    this.request<TranscribeAudioData, TranscribeAudioError>({
      path: `/routes/transcribe-audio`,
      method: "POST",
      body: data,
      type: ContentType.FormData,
      ...params,
    });

  /**
   * @description Handle OPTIONS preflight requests for /transcribe-audio for CORS.
   *
   * @tags dbtn/module:transcription, dbtn/hasAuth
   * @name transcribe_audio_options
   * @summary Transcribe Audio Options
   * @request OPTIONS:/routes/transcribe-audio
   */
  transcribe_audio_options = (params: RequestParams = {}) =>
    this.request<TranscribeAudioOptionsData, any>({
      path: `/routes/transcribe-audio`,
      method: "OPTIONS",
      ...params,
    });

  /**
   * No description
   *
   * @tags Zip Importer, dbtn/module:zip_importer, dbtn/hasAuth
   * @name upload_zip_archive
   * @summary Upload Zip Archive
   * @request POST:/routes/zip-importer/upload
   */
  upload_zip_archive = (data: BodyUploadZipArchive, params: RequestParams = {}) =>
    this.request<UploadZipArchiveData, UploadZipArchiveError>({
      path: `/routes/zip-importer/upload`,
      method: "POST",
      body: data,
      type: ContentType.FormData,
      ...params,
    });

  /**
   * @description Handles general-purpose file uploads using the Firebase Admin SDK. This ensures consistent authentication with the rest of the application.
   *
   * @tags Uploads, dbtn/module:uploads, dbtn/hasAuth
   * @name upload_general_file
   * @summary Upload General File
   * @request POST:/routes/uploads/upload_general_file
   */
  upload_general_file = (data: BodyUploadGeneralFile, params: RequestParams = {}) =>
    this.request<UploadGeneralFileData, UploadGeneralFileError>({
      path: `/routes/uploads/upload_general_file`,
      method: "POST",
      body: data,
      type: ContentType.FormData,
      ...params,
    });

  /**
   * @description Search the web for relevant technical discussions based on the query
   *
   * @tags dbtn/module:web_search, dbtn/hasAuth
   * @name search_web
   * @summary Search Web
   * @request POST:/routes/search
   */
  search_web = (data: WebSearchRequest, params: RequestParams = {}) =>
    this.request<SearchWebData, SearchWebError>({
      path: `/routes/search`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Reads the header row of a CSV file and returns the column names. This is used to populate the column mapping interface on the frontend.
   *
   * @tags importer, dbtn/module:importer, dbtn/hasAuth
   * @name get_csv_headers
   * @summary Get Csv Headers
   * @request POST:/routes/importer/get-csv-headers
   */
  get_csv_headers = (data: BodyGetCsvHeaders, params: RequestParams = {}) =>
    this.request<GetCsvHeadersData, GetCsvHeadersError>({
      path: `/routes/importer/get-csv-headers`,
      method: "POST",
      body: data,
      type: ContentType.FormData,
      ...params,
    });

  /**
   * @description Accepts a CSV, validates it, imports to Firestore, and creates/stores embeddings in the correct company-specific Pinecone index.
   *
   * @tags importer, dbtn/module:importer, dbtn/hasAuth
   * @name upload_historic_records_csv
   * @summary Upload Historic Records Csv
   * @request POST:/routes/importer/upload-historic-records-csv
   */
  upload_historic_records_csv = (data: BodyUploadHistoricRecordsCsv, params: RequestParams = {}) =>
    this.request<UploadHistoricRecordsCsvData, UploadHistoricRecordsCsvError>({
      path: `/routes/importer/upload-historic-records-csv`,
      method: "POST",
      body: data,
      type: ContentType.FormData,
      ...params,
    });

  /**
   * @description Deletes a single historic record from Firestore and Pinecone.
   *
   * @tags importer, dbtn/module:importer, dbtn/hasAuth
   * @name delete_historic_record
   * @summary Delete Historic Record
   * @request DELETE:/routes/importer/historic-records/{record_id}
   */
  delete_historic_record = ({ recordId, ...query }: DeleteHistoricRecordParams, params: RequestParams = {}) =>
    this.request<DeleteHistoricRecordData, DeleteHistoricRecordError>({
      path: `/routes/importer/historic-records/${recordId}`,
      method: "DELETE",
      query: query,
      ...params,
    });

  /**
   * @description Deletes multiple historic records from Firestore and Pinecone.
   *
   * @tags importer, dbtn/module:importer, dbtn/hasAuth
   * @name bulk_delete_historic_records
   * @summary Bulk Delete Historic Records
   * @request POST:/routes/importer/bulk-delete-historic-records
   */
  bulk_delete_historic_records = (data: BulkDeleteHistoricRecordsRequest, params: RequestParams = {}) =>
    this.request<BulkDeleteHistoricRecordsData, BulkDeleteHistoricRecordsError>({
      path: `/routes/importer/bulk-delete-historic-records`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Lists historic records for the user's company.
   *
   * @tags importer, dbtn/module:importer, dbtn/hasAuth
   * @name list_historic_records
   * @summary List Historic Records
   * @request GET:/routes/importer/historic-records
   */
  list_historic_records = (query: ListHistoricRecordsParams, params: RequestParams = {}) =>
    this.request<ListHistoricRecordsData, ListHistoricRecordsError>({
      path: `/routes/importer/historic-records`,
      method: "GET",
      query: query,
      ...params,
    });

  /**
   * @description Transcribe audio feedback using Google Cloud Speech-to-Text
   *
   * @tags dbtn/module:feedback, dbtn/hasAuth
   * @name transcribe_feedback
   * @summary Transcribe Feedback
   * @request POST:/routes/transcribe-feedback
   */
  transcribe_feedback = (data: FeedbackTranscriptionRequest, params: RequestParams = {}) =>
    this.request<TranscribeFeedbackData, TranscribeFeedbackError>({
      path: `/routes/transcribe-feedback`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * No description
   *
   * @tags dbtn/module:notifications, dbtn/hasAuth
   * @name send_email
   * @summary Send Email
   * @request POST:/routes/send-email
   */
  send_email = (data: EmailRequest, params: RequestParams = {}) =>
    this.request<SendEmailData, SendEmailError>({
      path: `/routes/send-email`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * No description
   *
   * @tags dbtn/module:response_generation, dbtn/hasAuth
   * @name generate_response
   * @summary Generate Response
   * @request POST:/routes/generate-response
   */
  generate_response = (data: ResponseRequest, params: RequestParams = {}) =>
    this.request<GenerateResponseData, GenerateResponseError>({
      path: `/routes/generate-response`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Stage 1: Receive serial number report from switch. Called by discovery script running on switch during initial boot. Verifies hardware identity and prepares full ZTP configuration. Args: body: Discovery report with MAC, serial, and optional vendor/model Returns: Discovery response with verification status and next steps Example Request: POST /ztp/discovery { "mac": "00:1B:21:D9:56:E3", "serial": "NVDA-QM9700-SP01-2024", "vendor": "NVIDIA", "model": "QM9700" } Example Response (Success): { "status": "VERIFIED", "message": "Identity verified. Ready for configuration.", "next_step": "https://yourapp.com/ztp/config/00:1B:21:D9:56:E3", "device_name": "IB-SPINE-01", "assigned_ip": "10.0.4.250" }
   *
   * @tags dbtn/module:ztp
   * @name handle_discovery_callback
   * @summary Handle Discovery Callback
   * @request POST:/routes/ztp/discovery
   */
  handle_discovery_callback = (data: DiscoveryReport, params: RequestParams = {}) =>
    this.request<HandleDiscoveryCallbackData, HandleDiscoveryCallbackError>({
      path: `/routes/ztp/discovery`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Stage 2: Provide full configuration script to verified switch. Called by switch after identity verification succeeds. Returns vendor-specific configuration script with all port IPs. Args: mac_address: MAC address of verified switch Returns: ConfigScriptResponse with bash script content Raises: HTTPException: If switch not verified or config not ready Example Request: GET /ztp/config/00:1B:21:D9:56:E3 Example Response: { "script": "#!/bin/bash cli configure terminal ...", "device_name": "IB-SPINE-01", "vendor": "NVIDIA", "model": "QM9700", "status": "READY" }
   *
   * @tags dbtn/module:ztp
   * @name get_full_ztp_config
   * @summary Get Full Ztp Config
   * @request GET:/routes/ztp/config/{mac_address}
   */
  get_full_ztp_config = ({ macAddress, ...query }: GetFullZtpConfigParams, params: RequestParams = {}) =>
    this.request<GetFullZtpConfigData, GetFullZtpConfigError>({
      path: `/routes/ztp/config/${macAddress}`,
      method: "GET",
      ...params,
    });

  /**
   * @description Generate minimal discovery script for unconfigured switch. This is the initial script sent via DHCP Option 67 that extracts the serial number and reports it back to the API. Args: mac_address: MAC address of switch (from DHCP request) Returns: Bash script as plain text Example Response: #!/bin/bash SERIAL=$(dmidecode -s system-serial-number) curl -X POST https://yourapp.com/ztp/discovery \ -d '{"mac":"00:1B:...","serial":"$SERIAL"}'
   *
   * @tags dbtn/module:ztp
   * @name get_discovery_script
   * @summary Get Discovery Script
   * @request GET:/routes/ztp/discovery-script/{mac_address}
   */
  get_discovery_script = ({ macAddress, ...query }: GetDiscoveryScriptParams, params: RequestParams = {}) =>
    this.request<GetDiscoveryScriptData, GetDiscoveryScriptError>({
      path: `/routes/ztp/discovery-script/${macAddress}`,
      method: "GET",
      ...params,
    });

  /**
   * @description Validate physical cabling against GPU-aware topology expectations. This is the critical "Verification" phase. After the switch executes its ZTP configuration and enables LLDP, it reports what neighbors it actually sees. We compare this against the expected GPU-to-Leaf mapping to detect mis-wires. **Why This Matters:** In a 4K GPU cluster with 32,768 cables, a single mis-wire causes: - ❌ 15-40% degradation in All-Reduce operations - ❌ Cross-plane traffic (defeats InfiniBand rail isolation) - ❌ Discovered only during expensive training runs ($50K+ delay) **This API Prevents:** - Wrong cables (Port 1 has Port 2's GPU) - Cross-rack errors (Rack 1 GPU on Rack 2 port) - Missing cables (expected connection, but no LLDP neighbor) Args: body: Cabling validation request with switch ID and LLDP neighbor list Returns: Validation report with per-port status and health percentage Example Request: POST /validate-cabling { "switch_id": "IB-LEAF-P0-L01", "plane_id": 0, "leaf_id": 1, "neighbors": [ {"port_id": "p1", "neighbor_hostname": "B200-Rack01-Srv01-GPU1-HCA0"}, {"port_id": "p2", "neighbor_hostname": "B200-Rack01-Srv02-GPU1-HCA0"} ] } Example Response (Mis-wire Detected): { "status": "COMPLETE", "cluster_healthy": false, "failed": 2, "swap_recommendations": ["🔄 Swap cables: Port 1 ↔ Port 2"] }
   *
   * @tags dbtn/module:ztp
   * @name validate_cabling
   * @summary Validate Cabling
   * @request POST:/routes/validate-cabling
   */
  validate_cabling = (data: CablingValidationRequest, params: RequestParams = {}) =>
    this.request<ValidateCablingData, ValidateCablingError>({
      path: `/routes/validate-cabling`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Upload a data center schematic for processing
   *
   * @tags dbtn/module:cluster_bringup
   * @name upload_schematic_file
   * @summary Upload Schematic File
   * @request POST:/routes/cluster-bringup/upload-schematic
   */
  upload_schematic_file = (data: BodyUploadSchematicFile, params: RequestParams = {}) =>
    this.request<UploadSchematicFileData, UploadSchematicFileError>({
      path: `/routes/cluster-bringup/upload-schematic`,
      method: "POST",
      body: data,
      type: ContentType.FormData,
      ...params,
    });

  /**
   * @description Configure color legend and processing options
   *
   * @tags dbtn/module:cluster_bringup
   * @name configure_schematic_processing
   * @summary Configure Schematic Processing
   * @request POST:/routes/cluster-bringup/configure-processing
   */
  configure_schematic_processing = (data: SchematicConfigRequest, params: RequestParams = {}) =>
    this.request<ConfigureSchematicProcessingData, ConfigureSchematicProcessingError>({
      path: `/routes/cluster-bringup/configure-processing`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Get current processing status
   *
   * @tags dbtn/module:cluster_bringup
   * @name get_processing_status
   * @summary Get Processing Status
   * @request GET:/routes/cluster-bringup/processing-status/{project_id}
   */
  get_processing_status = ({ projectId, ...query }: GetProcessingStatusParams, params: RequestParams = {}) =>
    this.request<GetProcessingStatusData, GetProcessingStatusError>({
      path: `/routes/cluster-bringup/processing-status/${projectId}`,
      method: "GET",
      ...params,
    });

  /**
   * @description Get extracted devices and connections
   *
   * @tags dbtn/module:cluster_bringup
   * @name get_extraction_results
   * @summary Get Extraction Results
   * @request GET:/routes/cluster-bringup/extraction-results/{project_id}
   */
  get_extraction_results = ({ projectId, ...query }: GetExtractionResultsParams, params: RequestParams = {}) =>
    this.request<GetExtractionResultsData, GetExtractionResultsError>({
      path: `/routes/cluster-bringup/extraction-results/${projectId}`,
      method: "GET",
      ...params,
    });

  /**
   * @description Export cabling matrix as CSV
   *
   * @tags dbtn/module:cluster_bringup
   * @name export_cabling_matrix
   * @summary Export Cabling Matrix
   * @request GET:/routes/cluster-bringup/export-cabling-matrix/{project_id}
   */
  export_cabling_matrix = ({ projectId, ...query }: ExportCablingMatrixParams, params: RequestParams = {}) =>
    this.request<ExportCablingMatrixData, ExportCablingMatrixError>({
      path: `/routes/cluster-bringup/export-cabling-matrix/${projectId}`,
      method: "GET",
      ...params,
    });

  /**
   * @description List all cluster bringup projects
   *
   * @tags dbtn/module:cluster_bringup
   * @name list_projects
   * @summary List Projects
   * @request GET:/routes/cluster-bringup/projects
   */
  list_projects = (params: RequestParams = {}) =>
    this.request<ListProjectsData, any>({
      path: `/routes/cluster-bringup/projects`,
      method: "GET",
      ...params,
    });

  /**
   * @description Delete a cluster bringup project and all associated data
   *
   * @tags dbtn/module:cluster_bringup
   * @name delete_project
   * @summary Delete Project
   * @request DELETE:/routes/cluster-bringup/project/{project_id}
   */
  delete_project = ({ projectId, ...query }: DeleteProjectParams, params: RequestParams = {}) =>
    this.request<DeleteProjectData, DeleteProjectError>({
      path: `/routes/cluster-bringup/project/${projectId}`,
      method: "DELETE",
      ...params,
    });

  /**
   * @description Upload asset inventory CSV and merge with extracted devices based on location hierarchy. Expected CSV columns: - Site, Room, Row, Rack, U-Position (or UPosition) - Serial Number (or SerialNumber) - Asset Tag (or AssetTag) - Manufacturer - Model - MAC Address (optional) - Purchase Date (optional) - Warranty Expiry (optional)
   *
   * @tags dbtn/module:cluster_bringup
   * @name upload_asset_inventory
   * @summary Upload Asset Inventory
   * @request POST:/routes/cluster-bringup/upload-asset-inventory/{project_id}
   */
  upload_asset_inventory = (
    { projectId, ...query }: UploadAssetInventoryParams,
    data: BodyUploadAssetInventory,
    params: RequestParams = {},
  ) =>
    this.request<UploadAssetInventoryData, UploadAssetInventoryError>({
      path: `/routes/cluster-bringup/upload-asset-inventory/${projectId}`,
      method: "POST",
      body: data,
      type: ContentType.FormData,
      ...params,
    });

  /**
   * @description Get validation report showing which devices have been verified against asset inventory.
   *
   * @tags dbtn/module:cluster_bringup
   * @name get_merge_validation
   * @summary Get Merge Validation
   * @request GET:/routes/cluster-bringup/merge-validation/{project_id}
   */
  get_merge_validation = ({ projectId, ...query }: GetMergeValidationParams, params: RequestParams = {}) =>
    this.request<GetMergeValidationData, GetMergeValidationError>({
      path: `/routes/cluster-bringup/merge-validation/${projectId}`,
      method: "GET",
      ...params,
    });

  /**
   * @description Download a sample CSV template for asset inventory with network-specific columns. Provides proper column headers and example data for procurement teams.
   *
   * @tags dbtn/module:cluster_bringup
   * @name download_asset_template
   * @summary Download Asset Template
   * @request GET:/routes/cluster-bringup/download-asset-template
   */
  download_asset_template = (params: RequestParams = {}) =>
    this.request<DownloadAssetTemplateData, any>({
      path: `/routes/cluster-bringup/download-asset-template`,
      method: "GET",
      ...params,
    });

  /**
   * @description Download the test 3-tier network schematic PNG for testing the cluster bringup workflow. Includes BACKEND_FABRIC, FRONTEND_FABRIC, and OOB_MANAGEMENT tiers with intentional validation issues.
   *
   * @tags dbtn/module:cluster_bringup
   * @name download_test_schematic
   * @summary Download Test Schematic
   * @request GET:/routes/cluster-bringup/download-test-schematic
   */
  download_test_schematic = (params: RequestParams = {}) =>
    this.request<DownloadTestSchematicData, any>({
      path: `/routes/cluster-bringup/download-test-schematic`,
      method: "GET",
      ...params,
    });

  /**
   * @description Download the test 3-tier asset inventory CSV for testing the cluster bringup workflow. Includes network segment, device role, and port information for validation testing.
   *
   * @tags dbtn/module:cluster_bringup
   * @name download_test_csv
   * @summary Download Test Csv
   * @request GET:/routes/cluster-bringup/download-test-csv
   */
  download_test_csv = (params: RequestParams = {}) =>
    this.request<DownloadTestCsvData, any>({
      path: `/routes/cluster-bringup/download-test-csv`,
      method: "GET",
      ...params,
    });

  /**
   * @description **DHCP Server Webhook Endpoint** Called by the DHCP server (ISC Kea, Infoblox, etc.) when a new device sends a DHCP DISCOVER packet during initial power-on. This is the "gatekeeper" that prevents wrong hardware from getting IPs. **Flow:** 1. DHCP server detects new MAC address 2. Calls this webhook with MAC and optional metadata 3. DHCPScraper verifies hardware identity 4. Returns SUCCESS (with IP) or BLOCKED (no IP assigned) **Security:** - If identity mismatch: Return HTTP 403 Forbidden - DHCP server should NOT assign IP on 403 response - Creates CRITICAL alert for Installation Lead **Integration Example (ISC Kea):** ```json { "hooks-libraries": [{ "library": "/usr/lib/kea/hooks/libdhcp_lease_cmds.so", "parameters": { "on-discover-webhook": "https://yourdomain.riff.works/routes/cluster-bringup/provisioning/discover/PROJECT_ID" } }] } ```
   *
   * @tags dbtn/module:cluster_bringup
   * @name dhcp_discovery_webhook
   * @summary Dhcp Discovery Webhook
   * @request POST:/routes/cluster-bringup/provisioning/discover/{project_id}
   */
  dhcp_discovery_webhook = (
    { projectId, ...query }: DhcpDiscoveryWebhookParams,
    data: DHCPDiscoverRequest,
    params: RequestParams = {},
  ) =>
    this.request<DhcpDiscoveryWebhookData, DhcpDiscoveryWebhookError>({
      path: `/routes/cluster-bringup/provisioning/discover/${projectId}`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description **Get Active Provisioning Alerts** Returns all unresolved alerts for the Installation Lead dashboard. Ordered by severity (CRITICAL first) and creation time. **Use Case:** Frontend dashboard polls this endpoint every 5 seconds to show real-time alerts when hardware mismatches are detected. **Alert Types:** - IDENTITY_MISMATCH (CRITICAL): Wrong switch at location - UNKNOWN_DEVICE (MEDIUM): MAC not in Day 0 plan - UNREACHABLE_SWITCH (HIGH): Switch booted but no serial response
   *
   * @tags dbtn/module:cluster_bringup
   * @name get_provisioning_alerts
   * @summary Get Provisioning Alerts
   * @request GET:/routes/cluster-bringup/provisioning/alerts/{project_id}
   */
  get_provisioning_alerts = ({ projectId, ...query }: GetProvisioningAlertsParams, params: RequestParams = {}) =>
    this.request<GetProvisioningAlertsData, GetProvisioningAlertsError>({
      path: `/routes/cluster-bringup/provisioning/alerts/${projectId}`,
      method: "GET",
      ...params,
    });

  /**
   * @description **Installation Lead Resolves Alert** Three resolution strategies: 1. **SWAP_HARDWARE**: Technician will physically move the switch. - Use when hardware was racked in wrong location - Marks alert as resolved, waits for physical correction 2. **UPDATE_INVENTORY**: Accept detected hardware as correct. - Use when Day 0 inventory was wrong, physical reality is correct - Updates Firestore with actual serial, unblocks device 3. **OVERRIDE_AND_PROCEED**: Proceed despite mismatch (DANGEROUS). - Use only when Installation Lead accepts the risk - ⚠️ Can lead to catastrophic configuration errors - Creates audit trail of override **Audit Trail:** All resolutions are logged with: - Who resolved it (user ID/email) - When it was resolved (timestamp) - Which strategy was used - Resolution outcome
   *
   * @tags dbtn/module:cluster_bringup
   * @name resolve_provisioning_alert
   * @summary Resolve Provisioning Alert
   * @request POST:/routes/cluster-bringup/provisioning/resolve
   */
  resolve_provisioning_alert = (data: ResolveAlertRequest, params: RequestParams = {}) =>
    this.request<ResolveProvisioningAlertData, ResolveProvisioningAlertError>({
      path: `/routes/cluster-bringup/provisioning/resolve`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description **Get Real-Time Provisioning Status** Returns overview of all devices and their provisioning state: - PROVISIONED (green): Hardware verified, IP assigned - BLOCKED_IDENTITY_MISMATCH (red): Wrong hardware detected - INVENTORY_UPDATED (yellow): Was corrected via UPDATE_INVENTORY - OVERRIDE_APPLIED (orange): Lead override applied (caution) - PENDING (grey): Waiting for power-on **Use Case:** Dashboard "Rack View" showing color-coded device status.
   *
   * @tags dbtn/module:cluster_bringup
   * @name get_provisioning_status
   * @summary Get Provisioning Status
   * @request GET:/routes/cluster-bringup/provisioning/status/{project_id}
   */
  get_provisioning_status = ({ projectId, ...query }: GetProvisioningStatusParams, params: RequestParams = {}) =>
    this.request<GetProvisioningStatusData, GetProvisioningStatusError>({
      path: `/routes/cluster-bringup/provisioning/status/${projectId}`,
      method: "GET",
      ...params,
    });

  /**
   * @description Get health status for a specific tier. Args: projectId: Project identifier tier: Tier name (BACKEND_FABRIC, STORAGE, COMPUTE)
   *
   * @tags dbtn/module:cluster_bringup
   * @name get_tier_health
   * @summary Get Tier Health
   * @request GET:/routes/cluster-bringup/tier-health/{project_id}/{tier}
   */
  get_tier_health = ({ projectId, tier, ...query }: GetTierHealthParams, params: RequestParams = {}) =>
    this.request<GetTierHealthData, GetTierHealthError>({
      path: `/routes/cluster-bringup/tier-health/${projectId}/${tier}`,
      method: "GET",
      ...params,
    });

  /**
   * @description Get overall cluster readiness status with all tiers.
   *
   * @tags dbtn/module:cluster_bringup
   * @name get_cluster_readiness
   * @summary Get Cluster Readiness
   * @request GET:/routes/cluster-bringup/cluster-readiness/{project_id}
   */
  get_cluster_readiness = ({ projectId, ...query }: GetClusterReadinessParams, params: RequestParams = {}) =>
    this.request<GetClusterReadinessData, GetClusterReadinessError>({
      path: `/routes/cluster-bringup/cluster-readiness/${projectId}`,
      method: "GET",
      ...params,
    });

  /**
   * @description Emergency override for tier dependency blocks. Requires CTO-level authorization token. Creates permanent audit trail.
   *
   * @tags dbtn/module:cluster_bringup
   * @name emergency_override
   * @summary Emergency Override
   * @request POST:/routes/cluster-bringup/emergency-override/{project_id}
   */
  emergency_override = (
    { projectId, ...query }: EmergencyOverrideParams,
    data: EmergencyOverrideRequest,
    params: RequestParams = {},
  ) =>
    this.request<EmergencyOverrideData, EmergencyOverrideError>({
      path: `/routes/cluster-bringup/emergency-override/${projectId}`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Get preview of IP allocations before deployment. Shows all planned GPU IP assignments with conflict detection.
   *
   * @tags dbtn/module:cluster_bringup
   * @name get_ip_allocation_preview
   * @summary Get Ip Allocation Preview
   * @request GET:/routes/cluster-bringup/ip-allocation-preview/{project_id}
   */
  get_ip_allocation_preview = ({ projectId, ...query }: GetIpAllocationPreviewParams, params: RequestParams = {}) =>
    this.request<GetIpAllocationPreviewData, GetIpAllocationPreviewError>({
      path: `/routes/cluster-bringup/ip-allocation-preview/${projectId}`,
      method: "GET",
      ...params,
    });

  /**
   * @description Register a new user using Firebase Admin SDK. This handles both the Firebase Auth account creation and Firestore document creation.
   *
   * @tags dbtn/module:user_registration, dbtn/hasAuth
   * @name register_user
   * @summary Register User
   * @request POST:/routes/register
   */
  register_user = (data: UserRegistrationRequest, params: RequestParams = {}) =>
    this.request<RegisterUserData, RegisterUserError>({
      path: `/routes/register`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description List all constraints for the authenticated user with optional filtering. Query Parameters: - domain: Filter by domain (e.g., 'dcdc') - category: Filter by category (e.g., 'safety') - severity: Filter by severity (e.g., 'critical') - active_only: If true, only return active constraints (default: true)
   *
   * @tags dbtn/module:constraints
   * @name list_constraints
   * @summary List Constraints
   * @request GET:/routes/constraints
   */
  list_constraints = (query: ListConstraintsParams, params: RequestParams = {}) =>
    this.request<ListConstraintsData, ListConstraintsError>({
      path: `/routes/constraints`,
      method: "GET",
      query: query,
      ...params,
    });

  /**
   * @description Create a new constraint for the authenticated user.
   *
   * @tags dbtn/module:constraints
   * @name create_new_constraint
   * @summary Create New Constraint
   * @request POST:/routes/constraints
   */
  create_new_constraint = (data: ConstraintCreate, params: RequestParams = {}) =>
    this.request<CreateNewConstraintData, CreateNewConstraintError>({
      path: `/routes/constraints`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Update an existing constraint. Only admins from the same company can update it.
   *
   * @tags dbtn/module:constraints
   * @name update_existing_constraint
   * @summary Update Existing Constraint
   * @request PUT:/routes/constraints/{constraint_id}
   */
  update_existing_constraint = (
    { constraintId, ...query }: UpdateExistingConstraintParams,
    data: ConstraintUpdate,
    params: RequestParams = {},
  ) =>
    this.request<UpdateExistingConstraintData, UpdateExistingConstraintError>({
      path: `/routes/constraints/${constraintId}`,
      method: "PUT",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Delete a constraint. Only admins from the same company can delete it.
   *
   * @tags dbtn/module:constraints
   * @name delete_existing_constraint
   * @summary Delete Existing Constraint
   * @request DELETE:/routes/constraints/{constraint_id}
   */
  delete_existing_constraint = (
    { constraintId, ...query }: DeleteExistingConstraintParams,
    params: RequestParams = {},
  ) =>
    this.request<DeleteExistingConstraintData, DeleteExistingConstraintError>({
      path: `/routes/constraints/${constraintId}`,
      method: "DELETE",
      ...params,
    });

  /**
   * @description Import pre-configured constraint templates for the authenticated user. Requires: company_admin or system_admin role Currently supports 'dcdc' (Data Center Deployment & Commissioning) templates.
   *
   * @tags dbtn/module:constraints
   * @name import_constraint_templates
   * @summary Import Constraint Templates
   * @request POST:/routes/constraints/import-templates
   */
  import_constraint_templates = (data: ImportTemplatesRequest, params: RequestParams = {}) =>
    this.request<ImportConstraintTemplatesData, ImportConstraintTemplatesError>({
      path: `/routes/constraints/import-templates`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Get metadata about available constraint template sets.
   *
   * @tags dbtn/module:constraints
   * @name get_available_constraint_templates
   * @summary Get Available Constraint Templates
   * @request GET:/routes/constraints/templates/available
   */
  get_available_constraint_templates = (params: RequestParams = {}) =>
    this.request<GetAvailableConstraintTemplatesData, any>({
      path: `/routes/constraints/templates/available`,
      method: "GET",
      ...params,
    });

  /**
   * @description Generates secure, temporary URLs for all media files associated with a specific expert tip.
   *
   * @tags Expert Tips Media, dbtn/module:expert_tips_media, dbtn/hasAuth
   * @name get_secure_media_urls_for_tip
   * @summary Get Secure URLs for an Expert Tip's Media
   * @request GET:/routes/expert-tips-media/{tip_id}
   */
  get_secure_media_urls_for_tip = ({ tipId, ...query }: GetSecureMediaUrlsForTipParams, params: RequestParams = {}) =>
    this.request<GetSecureMediaUrlsForTipData, GetSecureMediaUrlsForTipError>({
      path: `/routes/expert-tips-media/${tipId}`,
      method: "GET",
      ...params,
    });

  /**
   * @description Checks the status of Firebase Admin SDK initialization.
   *
   * @tags dbtn/module:firebase_admin, dbtn/hasAuth
   * @name firebase_status
   * @summary Firebase Status
   * @request GET:/routes/status
   */
  firebase_status = (params: RequestParams = {}) =>
    this.request<FirebaseStatusData, any>({
      path: `/routes/status`,
      method: "GET",
      ...params,
    });

  /**
   * @description Retrieve relevant document chunks from knowledge base based on query
   *
   * @tags dbtn/module:knowledge_retrieval, dbtn/hasAuth
   * @name retrieve_knowledge
   * @summary Retrieve Knowledge
   * @request POST:/routes/retrieve-knowledge
   */
  retrieve_knowledge = (data: RetrievalRequest, params: RequestParams = {}) =>
    this.request<RetrieveKnowledgeData, RetrieveKnowledgeError>({
      path: `/routes/retrieve-knowledge`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Get the namespace configuration for the authenticated user's company. Returns list of namespaces with their IDs and display names.
   *
   * @tags dbtn/module:knowledge_retrieval, dbtn/hasAuth
   * @name get_company_namespaces_endpoint
   * @summary Get Company Namespaces Endpoint
   * @request GET:/routes/company-namespaces
   */
  get_company_namespaces_endpoint = (params: RequestParams = {}) =>
    this.request<GetCompanyNamespacesEndpointData, any>({
      path: `/routes/company-namespaces`,
      method: "GET",
      ...params,
    });

  /**
   * @description Trigger topology sync for all nodes in project. This is the main entry point for topology synchronization. It queries Firestore for all COMPUTE nodes and applies topology labels to corresponding Kubernetes nodes. **When to call:** - After new nodes join the cluster - Periodically (every 5 minutes via cron) - After LLDP validation completes - After hardware changes or node replacement - For manual troubleshooting **Example:** ```bash curl -X POST http://localhost:8000/k8s-topology-sync/sync-topology/my-project ``` Args: projectId: Firestore project ID to sync Returns: SyncTopologyResponse with sync results Raises: HTTPException 500: If Firestore client not initialized or sync fails HTTPException 404: If project has no compute nodes
   *
   * @tags dbtn/module:k8s_topology_sync
   * @name sync_topology
   * @summary Sync Topology
   * @request POST:/routes/sync-topology/{project_id}
   */
  sync_topology = ({ projectId, ...query }: SyncTopologyParams, params: RequestParams = {}) =>
    this.request<SyncTopologyData, SyncTopologyError>({
      path: `/routes/sync-topology/${projectId}`,
      method: "POST",
      ...params,
    });

  /**
   * @description Get topology labels for a specific node. Useful for debugging and validation. Returns the current topology labels applied to a Kubernetes node. **Example:** ```bash curl http://localhost:8000/k8s-topology-sync/node-topology/dgx-su1-r02-s05 ``` Args: node_name: Kubernetes node name Returns: NodeTopologyResponse with topology labels Raises: HTTPException 404: If node not found in Kubernetes HTTPException 500: If kubectl fails
   *
   * @tags dbtn/module:k8s_topology_sync
   * @name get_node_topology
   * @summary Get Node Topology
   * @request GET:/routes/node-topology/{node_name}
   */
  get_node_topology = ({ nodeName, ...query }: GetNodeTopologyParams, params: RequestParams = {}) =>
    this.request<GetNodeTopologyData, GetNodeTopologyError>({
      path: `/routes/node-topology/${nodeName}`,
      method: "GET",
      ...params,
    });

  /**
   * @description Verify that all K8s nodes have topology labels. This is a health check endpoint. Use it to ensure topology sync is working correctly. **Health Status:** - HEALTHY: All nodes labeled - DEGRADED: 1-25% unlabeled - CRITICAL: >25% unlabeled **Example:** ```bash curl http://localhost:8000/k8s-topology-sync/verify-sync/my-project ``` Args: projectId: Firestore project ID Returns: VerifySyncResponse with health status
   *
   * @tags dbtn/module:k8s_topology_sync
   * @name verify_sync
   * @summary Verify Sync
   * @request GET:/routes/verify-sync/{project_id}
   */
  verify_sync = ({ projectId, ...query }: VerifySyncParams, params: RequestParams = {}) =>
    this.request<VerifySyncData, VerifySyncError>({
      path: `/routes/verify-sync/${projectId}`,
      method: "GET",
      ...params,
    });

  /**
   * @description Sync topology for a single node (faster than full sync). Useful for: - After node replacement - After hardware changes - After LLDP re-validation - Troubleshooting individual nodes **Example:** ```bash curl -X POST "http://localhost:8000/k8s-topology-sync/sync-single-node/dgx-su1-r02-s05?project_id=my-project" ``` Args: node_name: Node to sync projectId: Firestore project ID (query param) Returns: Dict with sync status
   *
   * @tags dbtn/module:k8s_topology_sync
   * @name sync_single_node
   * @summary Sync Single Node
   * @request POST:/routes/sync-single-node/{node_name}
   */
  sync_single_node = ({ nodeName, ...query }: SyncSingleNodeParams, params: RequestParams = {}) =>
    this.request<SyncSingleNodeData, SyncSingleNodeError>({
      path: `/routes/sync-single-node/${nodeName}`,
      method: "POST",
      query: query,
      ...params,
    });

  /**
   * @description Synthesizes speech from text using Google Cloud Text-to-Speech, caches it in db.storage, and returns a URL for instant playback.
   *
   * @tags dbtn/module:text_to_speech, dbtn/hasAuth
   * @name synthesize
   * @summary Synthesize
   * @request POST:/routes/synthesize
   */
  synthesize = (data: SynthesisRequest, params: RequestParams = {}) =>
    this.request<SynthesizeData, SynthesizeError>({
      path: `/routes/synthesize`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description This is the main entry point for the document processing worker. It's triggered by an HTTP request (e.g., from a Cloud Task or another service).
   *
   * @tags dbtn/module:doc_processor
   * @name process_document_worker
   * @summary Process Document Worker
   * @request POST:/routes/process-document-worker
   */
  process_document_worker = (data: WorkerPayload, params: RequestParams = {}) =>
    this.request<ProcessDocumentWorkerData, ProcessDocumentWorkerError>({
      path: `/routes/process-document-worker`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Parse and validate a Bill of Materials file (CSV or Excel).
   *
   * @tags onboarding, dbtn/module:onboarding
   * @name validate_bom_upload
   * @summary Validate Bom Upload
   * @request POST:/routes/onboarding/validate-bom
   */
  validate_bom_upload = (data: BodyValidateBomUpload, params: RequestParams = {}) =>
    this.request<ValidateBomUploadData, ValidateBomUploadError>({
      path: `/routes/onboarding/validate-bom`,
      method: "POST",
      body: data,
      type: ContentType.FormData,
      ...params,
    });

  /**
   * @description Return all available deployment templates.
   *
   * @tags onboarding, dbtn/module:onboarding
   * @name list_deployment_templates
   * @summary List Deployment Templates
   * @request GET:/routes/onboarding/templates
   */
  list_deployment_templates = (params: RequestParams = {}) =>
    this.request<ListDeploymentTemplatesData, any>({
      path: `/routes/onboarding/templates`,
      method: "GET",
      ...params,
    });

  /**
   * @description Generate ZTP config bundle and return as downloadable ZIP. Builds switch configs, DHCP config, cabling matrix, and setup guide based on the user's topology configuration and returns as ZIP bytes.
   *
   * @tags onboarding, dbtn/module:onboarding
   * @name generate_onboarding_configs
   * @summary Generate Onboarding Configs
   * @request POST:/routes/onboarding/generate-configs
   */
  generate_onboarding_configs = (data: GenerateConfigRequest, params: RequestParams = {}) =>
    this.request<GenerateOnboardingConfigsData, GenerateOnboardingConfigsError>({
      path: `/routes/onboarding/generate-configs`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Get pending user requests for approval
   *
   * @tags dbtn/module:user_management, dbtn/hasAuth
   * @name get_pending_users
   * @summary Get Pending Users
   * @request GET:/routes/admin/pending-users
   */
  get_pending_users = (params: RequestParams = {}) =>
    this.request<GetPendingUsersData, any>({
      path: `/routes/admin/pending-users`,
      method: "GET",
      ...params,
    });

  /**
   * @description Approve or reject a user request
   *
   * @tags dbtn/module:user_management, dbtn/hasAuth
   * @name approve_reject_user
   * @summary Approve Reject User
   * @request POST:/routes/admin/approve-user
   */
  approve_reject_user = (data: ApproveRejectRequest, params: RequestParams = {}) =>
    this.request<ApproveRejectUserData, ApproveRejectUserError>({
      path: `/routes/admin/approve-user`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Get list of available domains for assignment
   *
   * @tags dbtn/module:user_management, dbtn/hasAuth
   * @name get_available_domains
   * @summary Get Available Domains
   * @request GET:/routes/admin/domains
   */
  get_available_domains = (params: RequestParams = {}) =>
    this.request<GetAvailableDomainsData, any>({
      path: `/routes/admin/domains`,
      method: "GET",
      ...params,
    });

  /**
   * @description Assign a specific domain to a user (Company Admin only)
   *
   * @tags dbtn/module:user_management, dbtn/hasAuth
   * @name assign_user_domain
   * @summary Assign User Domain
   * @request POST:/routes/admin/assign-domain
   */
  assign_user_domain = (data: AssignDomainRequest, params: RequestParams = {}) =>
    this.request<AssignUserDomainData, AssignUserDomainError>({
      path: `/routes/admin/assign-domain`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Get all users in the system
   *
   * @tags dbtn/module:user_management, dbtn/hasAuth
   * @name get_all_users
   * @summary Get All Users
   * @request GET:/routes/admin/users
   */
  get_all_users = (query: GetAllUsersParams, params: RequestParams = {}) =>
    this.request<GetAllUsersData, GetAllUsersError>({
      path: `/routes/admin/users`,
      method: "GET",
      query: query,
      ...params,
    });

  /**
   * @description Handles the creation of the expert tip database entry. This endpoint assumes media files have already been uploaded to GCS and their URLs are provided in the request.
   *
   * @tags Expert Tips, dbtn/module:expert_tips, dbtn/hasAuth
   * @name create_expert_tip_entry
   * @summary Creates an expert tip entry in Firestore after files are uploaded
   * @request POST:/routes/expert-tips/create-entry
   */
  create_expert_tip_entry = (data: CreateExpertTipEntryRequest, params: RequestParams = {}) =>
    this.request<CreateExpertTipEntryData, CreateExpertTipEntryError>({
      path: `/routes/expert-tips/create-entry`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Create a new customer account. This is the entry point for new customer signups. Creates isolated namespace in Firestore and sets up admin user. **Example:** ```bash curl -X POST http://localhost:8000/customer-management/customers       -H "Content-Type: application/json"       -d '{ "company_name": "NVIDIA Corporation", "admin_email": "admin@nvidia.com", "license_tier": "enterprise", "metadata": {"industry": "AI", "employee_count": 10000} }' ``` Args: request: CreateCustomerRequest Returns: CustomerResponse with customer_id Raises: HTTPException 400: If license_tier invalid or customer exists HTTPException 500: If CustomerManager not initialized
   *
   * @tags dbtn/module:customer_management
   * @name create_customer
   * @summary Create Customer
   * @request POST:/routes/customers
   */
  create_customer = (data: CreateCustomerRequest, params: RequestParams = {}) =>
    this.request<CreateCustomerData, CreateCustomerError>({
      path: `/routes/customers`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description List all customers. **Security:** Platform admin only. This endpoint is for internal operations team, not customer-facing. Args: status: Filter by status ("active", "trial", "suspended") license_tier: Filter by tier ("starter", "professional", "enterprise") limit: Max results (default 100) x_platform_admin: Admin auth token Returns: List of CustomerResponse Raises: HTTPException 403: If not platform admin
   *
   * @tags dbtn/module:customer_management
   * @name list_customers
   * @summary List Customers
   * @request GET:/routes/customers
   */
  list_customers = (query: ListCustomersParams, params: RequestParams = {}) =>
    this.request<ListCustomersData, ListCustomersError>({
      path: `/routes/customers`,
      method: "GET",
      query: query,
      ...params,
    });

  /**
   * @description Get customer details by ID. **Security:** Users can only access their own customer data. Platform admins can access any customer. Args: customer_id: Customer ID x_customer_id: Customer ID from header (for auth check) Returns: CustomerResponse Raises: HTTPException 403: If trying to access another customer's data HTTPException 404: If customer not found
   *
   * @tags dbtn/module:customer_management
   * @name get_customer
   * @summary Get Customer
   * @request GET:/routes/customers/{customer_id}
   */
  get_customer = ({ customerId, ...query }: GetCustomerParams, params: RequestParams = {}) =>
    this.request<GetCustomerData, GetCustomerError>({
      path: `/routes/customers/${customerId}`,
      method: "GET",
      ...params,
    });

  /**
   * @description Update customer data. **Allowed updates:** - company_name (if legal name changes) - metadata (industry, employee_count, etc.) - status (admin only - use suspend/activate endpoints instead) Args: customer_id: Customer ID request: UpdateCustomerRequest x_customer_id: Customer ID from header (for auth check) Returns: Updated CustomerResponse Raises: HTTPException 403: If unauthorized HTTPException 404: If customer not found
   *
   * @tags dbtn/module:customer_management
   * @name update_customer
   * @summary Update Customer
   * @request PUT:/routes/customers/{customer_id}
   */
  update_customer = (
    { customerId, ...query }: UpdateCustomerParams,
    data: UpdateCustomerRequest,
    params: RequestParams = {},
  ) =>
    this.request<UpdateCustomerData, UpdateCustomerError>({
      path: `/routes/customers/${customerId}`,
      method: "PUT",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Delete a customer and ALL their data. ⚠️ **IRREVERSIBLE OPERATION** **Platform admin only.** Deletes: - Customer account - All infrastructure data - All projects - All users - All audit logs Use case: Customer requests data deletion (GDPR right to be forgotten). Args: customer_id: Customer ID confirm: Must be True to actually delete x_platform_admin: Admin auth token Returns: Success message Raises: HTTPException 403: If not platform admin HTTPException 400: If confirm not True
   *
   * @tags dbtn/module:customer_management
   * @name delete_customer
   * @summary Delete Customer
   * @request DELETE:/routes/customers/{customer_id}
   */
  delete_customer = ({ customerId, ...query }: DeleteCustomerParams, params: RequestParams = {}) =>
    this.request<DeleteCustomerData, DeleteCustomerError>({
      path: `/routes/customers/${customerId}`,
      method: "DELETE",
      query: query,
      ...params,
    });

  /**
   * @description Upgrade customer's license tier. **Upgrade paths:** - starter → professional - starter → enterprise - professional → enterprise Downgrades are not allowed (contact support for special cases). Args: customer_id: Customer ID request: UpgradeLicenseRequest x_customer_id: Customer ID from header (for auth check) Returns: Updated CustomerResponse Raises: HTTPException 400: If downgrade attempted or invalid tier HTTPException 403: If unauthorized
   *
   * @tags dbtn/module:customer_management
   * @name upgrade_license
   * @summary Upgrade License
   * @request POST:/routes/customers/{customer_id}/upgrade
   */
  upgrade_license = (
    { customerId, ...query }: UpgradeLicenseParams,
    data: UpgradeLicenseRequest,
    params: RequestParams = {},
  ) =>
    this.request<UpgradeLicenseData, UpgradeLicenseError>({
      path: `/routes/customers/${customerId}/upgrade`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Suspend a customer account. **Platform admin only.** Suspended customers: - Cannot log in - Cannot access any features - Data is retained (not deleted) - Can be reactivated Common reasons: Payment failure, policy violation, security breach. Args: customer_id: Customer ID request: SuspendCustomerRequest x_platform_admin: Admin auth token Returns: Success message Raises: HTTPException 403: If not platform admin
   *
   * @tags dbtn/module:customer_management
   * @name suspend_customer
   * @summary Suspend Customer
   * @request POST:/routes/customers/{customer_id}/suspend
   */
  suspend_customer = (
    { customerId, ...query }: SuspendCustomerParams,
    data: SuspendCustomerRequest,
    params: RequestParams = {},
  ) =>
    this.request<SuspendCustomerData, SuspendCustomerError>({
      path: `/routes/customers/${customerId}/suspend`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Activate a suspended customer. **Platform admin only.** Args: customer_id: Customer ID x_platform_admin: Admin auth token Returns: Success message Raises: HTTPException 403: If not platform admin
   *
   * @tags dbtn/module:customer_management
   * @name activate_customer
   * @summary Activate Customer
   * @request POST:/routes/customers/{customer_id}/activate
   */
  activate_customer = ({ customerId, ...query }: ActivateCustomerParams, params: RequestParams = {}) =>
    this.request<ActivateCustomerData, ActivateCustomerError>({
      path: `/routes/customers/${customerId}/activate`,
      method: "POST",
      ...params,
    });

  /**
   * @description Check GPU quota usage for customer. Returns current GPU count vs license limit. Used to enforce quota and prompt upgrades. Args: customer_id: Customer ID x_customer_id: Customer ID from header (for auth check) Returns: QuotaResponse Raises: HTTPException 403: If unauthorized HTTPException 404: If customer not found
   *
   * @tags dbtn/module:customer_management
   * @name check_quota
   * @summary Check Quota
   * @request GET:/routes/customers/{customer_id}/quota
   */
  check_quota = ({ customerId, ...query }: CheckQuotaParams, params: RequestParams = {}) =>
    this.request<CheckQuotaData, CheckQuotaError>({
      path: `/routes/customers/${customerId}/quota`,
      method: "GET",
      ...params,
    });

  /**
   * @description Deploy K3s control plane on admin node. This is a ONE-TIME operation to initialize the cluster. Subsequent nodes join via /join-node. **Usage:** ``` POST /kubernetes/bootstrap { "control_plane_ip": "10.0.0.10" } ```
   *
   * @tags dbtn/module:kubernetes
   * @name bootstrap_control_plane_endpoint
   * @summary Bootstrap Control Plane Endpoint
   * @request POST:/routes/kubernetes/bootstrap
   */
  bootstrap_control_plane_endpoint = (data: BootstrapRequest, params: RequestParams = {}) =>
    this.request<BootstrapControlPlaneEndpointData, BootstrapControlPlaneEndpointError>({
      path: `/routes/kubernetes/bootstrap`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Add worker node to K8s cluster after ZTP provisioning. Called by DHCPScraper after OS installation completes. Only COMPUTE tier nodes join the cluster. **Usage:** ``` POST /kubernetes/join-node { "node_ip": "10.244.1.5", "node_hostname": "SU1-RACK01-SRV01", "tier": "COMPUTE", "gpu_count": 8 } ```
   *
   * @tags dbtn/module:kubernetes
   * @name join_worker_node
   * @summary Join Worker Node
   * @request POST:/routes/kubernetes/join-node
   */
  join_worker_node = (data: JoinNodeRequest, params: RequestParams = {}) =>
    this.request<JoinWorkerNodeData, JoinWorkerNodeError>({
      path: `/routes/kubernetes/join-node`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description List all K8s nodes with GPU inventory. Returns detailed info for each node including: - GPU count (from nvidia.com/gpu resource) - Node status (Ready/NotReady) - Tier label (COMPUTE/STORAGE/ADMIN) - Provisioning source (dhcp-scraper, manual, etc.) **Usage:** ``` GET /kubernetes/nodes ```
   *
   * @tags dbtn/module:kubernetes
   * @name list_cluster_nodes
   * @summary List Cluster Nodes
   * @request GET:/routes/kubernetes/nodes
   */
  list_cluster_nodes = (params: RequestParams = {}) =>
    this.request<ListClusterNodesData, any>({
      path: `/routes/kubernetes/nodes`,
      method: "GET",
      ...params,
    });

  /**
   * @description Get cluster health metrics. Returns: - Total/Ready node counts - Total GPU count across cluster - Control plane IP **Usage:** ``` GET /kubernetes/cluster-status ```
   *
   * @tags dbtn/module:kubernetes
   * @name get_cluster_status
   * @summary Get Cluster Status
   * @request GET:/routes/kubernetes/cluster-status
   */
  get_cluster_status = (params: RequestParams = {}) =>
    this.request<GetClusterStatusData, any>({
      path: `/routes/kubernetes/cluster-status`,
      method: "GET",
      ...params,
    });

  /**
   * @description Get detailed info for a specific node. Args: node_name: K8s node name (e.g., SU1-RACK01-SRV01) **Usage:** ``` GET /kubernetes/node/SU1-RACK01-SRV01 ```
   *
   * @tags dbtn/module:kubernetes
   * @name get_node_details
   * @summary Get Node Details
   * @request GET:/routes/kubernetes/node/{node_name}
   */
  get_node_details = ({ nodeName, ...query }: GetNodeDetailsParams, params: RequestParams = {}) =>
    this.request<GetNodeDetailsData, GetNodeDetailsError>({
      path: `/routes/kubernetes/node/${nodeName}`,
      method: "GET",
      ...params,
    });

  /**
   * @description Handle ZTP completion webhook and trigger K8s worker join. Called by switches/nodes after ZTP script execution completes. For COMPUTE tier nodes, this triggers automatic K8s cluster join. **Workflow:** 1. ZTP script completes OS installation 2. Node sends POST /kubernetes/ztp-complete 3. Lookup node in Firestore (check k8s_join_pending flag) 4. If COMPUTE node → trigger K8s join via K8sProvisioner 5. Return status **Usage:** ``` POST /kubernetes/ztp-complete { "node_hostname": "SU1-RACK01-SRV01", "node_ip": "10.244.1.5", "mac_address": "00:1A:2B:3C:4D:5E", "ztp_status": "SUCCESS" } ```
   *
   * @tags dbtn/module:kubernetes
   * @name handle_ztp_completion
   * @summary Handle Ztp Completion
   * @request POST:/routes/kubernetes/ztp-complete
   */
  handle_ztp_completion = (data: ZTPCompletionRequest, params: RequestParams = {}) =>
    this.request<HandleZtpCompletionData, HandleZtpCompletionError>({
      path: `/routes/kubernetes/ztp-complete`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * No description
   *
   * @tags dbtn/module:technician_uploads, dbtn/hasAuth
   * @name upload_technician_file_v2
   * @summary Upload Technician File V2
   * @request POST:/routes/technician_uploads/upload_file
   */
  upload_technician_file_v2 = (data: BodyUploadTechnicianFileV2, params: RequestParams = {}) =>
    this.request<UploadTechnicianFileV2Data, UploadTechnicianFileV2Error>({
      path: `/routes/technician_uploads/upload_file`,
      method: "POST",
      body: data,
      type: ContentType.FormData,
      ...params,
    });

  /**
   * @description Takes a session_id, fetches the full session context from Firestore, and then uses Google Gemini to generate a professional report draft.
   *
   * @tags technicianreport, dbtn/module:technicianreport, dbtn/hasAuth
   * @name generate_llm_draft_report
   * @summary Generate Llm Draft Report
   * @request POST:/routes/technicianreport/generate
   */
  generate_llm_draft_report = (data: ReportGenerationRequest, params: RequestParams = {}) =>
    this.request<GenerateLlmDraftReportData, GenerateLlmDraftReportError>({
      path: `/routes/technicianreport/generate`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Saves the final report. It now fetches the 'assignmentLocation' from the original troubleshooting session instead of receiving coordinates.
   *
   * @tags technicianreport, dbtn/module:technicianreport, dbtn/hasAuth
   * @name save_finalized_report
   * @summary Save Finalized Report
   * @request POST:/routes/technicianreport/save
   */
  save_finalized_report = (data: ReportSaveRequest, params: RequestParams = {}) =>
    this.request<SaveFinalizedReportData, SaveFinalizedReportError>({
      path: `/routes/technicianreport/save`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Retrieves all troubleshooting reports filed by the currently authenticated technician, ordered from newest to oldest.
   *
   * @tags technicianreport, dbtn/module:technicianreport, dbtn/hasAuth
   * @name get_my_reports
   * @summary Get My Reports
   * @request GET:/routes/technicianreport/my-reports
   */
  get_my_reports = (params: RequestParams = {}) =>
    this.request<GetMyReportsData, any>({
      path: `/routes/technicianreport/my-reports`,
      method: "GET",
      ...params,
    });

  /**
   * @description Retrieves a single troubleshooting report by its document ID from Firestore.
   *
   * @tags technicianreport, dbtn/module:technicianreport, dbtn/hasAuth
   * @name get_specific_report
   * @summary Get Specific Report
   * @request GET:/routes/technicianreport/{report_id}
   */
  get_specific_report = ({ reportId, ...query }: GetSpecificReportParams, params: RequestParams = {}) =>
    this.request<GetSpecificReportData, GetSpecificReportError>({
      path: `/routes/technicianreport/${reportId}`,
      method: "GET",
      ...params,
    });

  /**
   * @description Creates a user account with proper hierarchical approval workflow: - System Admins are auto-approved - Company Admins require System Admin approval - Technicians require Company Admin approval
   *
   * @tags dbtn/module:direct_user_approval, dbtn/hasAuth
   * @name direct_approve_user2
   * @summary Direct Approve User2
   * @request POST:/routes/direct-approve-user2
   */
  direct_approve_user2 = (data: DirectRegistrationRequest, params: RequestParams = {}) =>
    this.request<DirectApproveUser2Data, DirectApproveUser2Error>({
      path: `/routes/direct-approve-user2`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Directly approve or reject a user without needing the admin UI
   *
   * @tags dbtn/module:approve_user_script, dbtn/hasAuth
   * @name direct_approve_user
   * @summary Direct Approve User
   * @request POST:/routes/direct-approve
   */
  direct_approve_user = (data: DirectApproveRequest, params: RequestParams = {}) =>
    this.request<DirectApproveUserData, DirectApproveUserError>({
      path: `/routes/direct-approve`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Uploads a document, saves it to GCS, and enqueues a processing task.
   *
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name upload_document
   * @summary Upload Document
   * @request POST:/routes/upload-document
   */
  upload_document = (data: BodyUploadDocument, params: RequestParams = {}) =>
    this.request<UploadDocumentData, UploadDocumentError>({
      path: `/routes/upload-document`,
      method: "POST",
      body: data,
      type: ContentType.FormData,
      ...params,
    });

  /**
   * No description
   *
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name get_document_status
   * @summary Get Document Status
   * @request GET:/routes/documents/{doc_id}/status
   */
  get_document_status = ({ docId, ...query }: GetDocumentStatusParams, params: RequestParams = {}) =>
    this.request<GetDocumentStatusData, GetDocumentStatusError>({
      path: `/routes/documents/${docId}/status`,
      method: "GET",
      ...params,
    });

  /**
   * @description List documents (admin only)
   *
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name list_documents
   * @summary List Documents
   * @request GET:/routes/documents
   */
  list_documents = (query: ListDocumentsParams, params: RequestParams = {}) =>
    this.request<ListDocumentsData, ListDocumentsError>({
      path: `/routes/documents`,
      method: "GET",
      query: query,
      ...params,
    });

  /**
   * @description Provides a document count summary for a company admin.
   *
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name get_document_metrics_summary
   * @summary Get Document Metrics Summary
   * @request GET:/routes/document-metrics-summary
   */
  get_document_metrics_summary = (params: RequestParams = {}) =>
    this.request<GetDocumentMetricsSummaryData, any>({
      path: `/routes/document-metrics-summary`,
      method: "GET",
      ...params,
    });

  /**
   * @description Optimized version of get_document. Uses a global Firestore client to avoid re-initialization and disk I/O on every call.
   *
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name get_document_optimal
   * @summary Get Document Optimal
   * @request GET:/routes/documents/{doc_id}/get_document_optimal
   */
  get_document_optimal = ({ docId, ...query }: GetDocumentOptimalParams, params: RequestParams = {}) =>
    this.request<GetDocumentOptimalData, GetDocumentOptimalError>({
      path: `/routes/documents/${docId}/get_document_optimal`,
      method: "GET",
      ...params,
    });

  /**
   * No description
   *
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name get_document
   * @summary Get Document
   * @request GET:/routes/documents/{doc_id}
   */
  get_document = ({ docId, ...query }: GetDocumentParams, params: RequestParams = {}) =>
    this.request<GetDocumentData, GetDocumentError>({
      path: `/routes/documents/${docId}`,
      method: "GET",
      ...params,
    });

  /**
   * @description Deletes a document and its associated data from Firestore, GCS, and Pinecone. This is a permanent action.
   *
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name delete_document
   * @summary Delete Document
   * @request DELETE:/routes/documents/{doc_id}
   */
  delete_document = ({ docId, ...query }: DeleteDocumentParams, params: RequestParams = {}) =>
    this.request<DeleteDocumentData, DeleteDocumentError>({
      path: `/routes/documents/${docId}`,
      method: "DELETE",
      ...params,
    });

  /**
   * @description Generates a secure, short-lived URL to view a document.
   *
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name get_secure_document_url
   * @summary Get Secure Document Url
   * @request GET:/routes/get-secure-document-url/{document_id}
   */
  get_secure_document_url = ({ documentId, ...query }: GetSecureDocumentUrlParams, params: RequestParams = {}) =>
    this.request<GetSecureDocumentUrlData, GetSecureDocumentUrlError>({
      path: `/routes/get-secure-document-url/${documentId}`,
      method: "GET",
      ...params,
    });

  /**
   * @description Update document metadata (admin only)
   *
   * @tags dbtn/module:document_management, dbtn/hasAuth
   * @name update_document
   * @summary Update Document
   * @request PUT:/routes/documents/{document_id}
   */
  update_document = (
    { documentId, ...query }: UpdateDocumentParams,
    data: DocumentUpdateRequest,
    params: RequestParams = {},
  ) =>
    this.request<UpdateDocumentData, UpdateDocumentError>({
      path: `/routes/documents/${documentId}`,
      method: "PUT",
      body: data,
      type: ContentType.Json,
      ...params,
    });

  /**
   * @description Get admin dashboard metrics
   *
   * @tags dbtn/module:admin, dbtn/hasAuth
   * @name get_admin_metrics
   * @summary Get Admin Metrics
   * @request GET:/routes/admin/metrics
   */
  get_admin_metrics = (query: GetAdminMetricsParams, params: RequestParams = {}) =>
    this.request<GetAdminMetricsData, GetAdminMetricsError>({
      path: `/routes/admin/metrics`,
      method: "GET",
      query: query,
      ...params,
    });

  /**
   * @description Dummy endpoint to reprocess a document that might be stuck. In a real scenario, this would trigger a background task.
   *
   * @tags dbtn/module:admin, dbtn/hasAuth
   * @name reprocess_stuck_document
   * @summary Reprocess Stuck Document
   * @request POST:/routes/admin/reprocess_document
   */
  reprocess_stuck_document = (data: ReprocessRequest, params: RequestParams = {}) =>
    this.request<ReprocessStuckDocumentData, ReprocessStuckDocumentError>({
      path: `/routes/admin/reprocess_document`,
      method: "POST",
      body: data,
      type: ContentType.Json,
      ...params,
    });
}
