/** AddEntryResponse */
export interface AddEntryResponse {
  /** Message */
  message: string;
  /** Pinecone Vector Id */
  pinecone_vector_id: string;
}

/** AddSessionRequest */
export interface AddSessionRequest {
  /** Sessionid */
  sessionId: string;
  /**
   * Target Index
   * @default "troubleshooting-sessions"
   */
  target_index?: string | null;
}

/** ApproveRejectRequest */
export interface ApproveRejectRequest {
  /**
   * Userid
   * Document ID of the pending request to approve/reject
   */
  userId: string;
  /** Approve */
  approve: boolean;
  /** Rejectionreason */
  rejectionReason?: string | null;
  /**
   * Role
   * Role to assign to the user (technician or company_admin)
   */
  role?: string | null;
}

/** ApproveRejectResponse */
export interface ApproveRejectResponse {
  /** Success */
  success: boolean;
  /** Message */
  message: string;
  /** Userid */
  userId: string;
}

/**
 * AssetInventoryUploadResponse
 * Response model for asset inventory upload
 */
export interface AssetInventoryUploadResponse {
  /** Success */
  success: boolean;
  /** Matchedcount */
  matchedCount: number;
  /** Unmatchedschematicdevices */
  unmatchedSchematicDevices: string[];
  /** Unmatchedinventorydevices */
  unmatchedInventoryDevices: Record<string, any>[];
  /** Validationreport */
  validationReport: string;
}

/** AssignDomainRequest */
export interface AssignDomainRequest {
  /**
   * Userid
   * User ID to assign domain to
   */
  userId: string;
  /**
   * Domain
   * Domain key to assign (must be one of the valid domains)
   */
  domain: string;
}

/** AssignDomainResponse */
export interface AssignDomainResponse {
  /** Success */
  success: boolean;
  /** Message */
  message: string;
  /** Userid */
  userId: string;
  /** Assigneddomain */
  assignedDomain: string;
}

/**
 * AvailableTemplatesResponse
 * Response model for available templates
 */
export interface AvailableTemplatesResponse {
  /** Templates */
  templates: Record<string, TemplateMetadata>;
}

/** Body_get_csv_headers */
export interface BodyGetCsvHeaders {
  /**
   * File
   * @format binary
   */
  file: File;
}

/** Body_transcribe_audio */
export interface BodyTranscribeAudio {
  /**
   * Audio
   * @format binary
   */
  audio: File;
}

/** Body_upload_asset_inventory */
export interface BodyUploadAssetInventory {
  /**
   * File
   * @format binary
   */
  file: File;
}

/** Body_upload_document */
export interface BodyUploadDocument {
  /**
   * File
   * @format binary
   */
  file: File;
  /** Title */
  title: string;
  /** Description */
  description?: string | null;
  /**
   * Target Index
   * @default "general"
   */
  target_index?: string | null;
  /** Tags */
  tags?: string | null;
}

/** Body_upload_general_file */
export interface BodyUploadGeneralFile {
  /**
   * File
   * @format binary
   */
  file: File;
}

/** Body_upload_historic_records_csv */
export interface BodyUploadHistoricRecordsCsv {
  /**
   * File
   * @format binary
   */
  file: File;
  /** Mapping */
  mapping: string;
  /**
   * Target Index
   * @default "historic"
   */
  target_index?: string;
}

/** Body_upload_schematic_file */
export interface BodyUploadSchematicFile {
  /**
   * Schematic File
   * @format binary
   */
  schematic_file: File;
}

/** Body_upload_technician_file_v2 */
export interface BodyUploadTechnicianFileV2 {
  /** Sessionid */
  sessionId: string;
  /**
   * File
   * @format binary
   */
  file: File;
}

/** Body_upload_zip_archive */
export interface BodyUploadZipArchive {
  /** Companyid */
  companyId: string;
  /**
   * File
   * @format binary
   */
  file: File;
  /**
   * Target Index
   * @default "general"
   */
  target_index?: string;
}

/** Body_validate_bom_upload */
export interface BodyValidateBomUpload {
  /**
   * File
   * @format binary
   */
  file: File;
}

/** BomDevice */
export interface BomDevice {
  /** Model */
  model: string;
  /** Matched Model */
  matched_model: string;
  /** Serial */
  serial: string;
  /** Quantity */
  quantity: number;
  /** Role */
  role: string;
  /** Supported */
  supported: boolean;
}

/** BomValidationResponse */
export interface BomValidationResponse {
  /** Devices */
  devices: BomDevice[];
  /** Warnings */
  warnings: string[];
  /** Errors */
  errors: string[];
  /** Gpu Count */
  gpu_count: number;
  /** Switch Count */
  switch_count: number;
  /** Valid */
  valid: boolean;
}

/**
 * BootstrapRequest
 * Request to bootstrap K3s control plane.
 */
export interface BootstrapRequest {
  /** Control Plane Ip */
  control_plane_ip: string;
}

/**
 * BootstrapResponse
 * Control plane deployment result.
 */
export interface BootstrapResponse {
  /** Status */
  status: string;
  /** Control Plane Ip */
  control_plane_ip: string;
  /** Kubeconfig */
  kubeconfig?: string | null;
  /** Error */
  error?: string | null;
}

/** BulkDeleteHistoricRecordsRequest */
export interface BulkDeleteHistoricRecordsRequest {
  /** Record Ids */
  record_ids: string[];
  /**
   * Target Index
   * @default "historic"
   */
  target_index?: string;
}

/** BulkDeleteHistoricRecordsResponse */
export interface BulkDeleteHistoricRecordsResponse {
  /** Success */
  success: boolean;
  /** Deleted Count */
  deleted_count: number;
  /** Failed Count */
  failed_count: number;
  /** Message */
  message: string;
}

/** CSVHeadersResponse */
export interface CSVHeadersResponse {
  /** Headers */
  headers: string[];
}

/** CSVUploadResponse */
export interface CSVUploadResponse {
  /** Success */
  success: boolean;
  /** Records Processed */
  records_processed: number;
  /** Errors */
  errors: string[];
  /** Message */
  message: string;
}

/**
 * CablingValidationRequest
 * Request to validate cabling against topology expectations.
 */
export interface CablingValidationRequest {
  /** Switch Id */
  switch_id: string;
  /** Plane Id */
  plane_id: number;
  /** Leaf Id */
  leaf_id: number;
  /** Neighbors */
  neighbors: LLDPNeighbor[];
}

/**
 * CablingValidationResponse
 * Complete cabling validation report.
 */
export interface CablingValidationResponse {
  /** Status */
  status: string;
  /** Switch Id */
  switch_id: string;
  /** Plane Id */
  plane_id: number;
  /** Leaf Id */
  leaf_id: number;
  /** Cluster Healthy */
  cluster_healthy: boolean;
  /** Total Ports */
  total_ports: number;
  /** Passed */
  passed: number;
  /** Failed */
  failed: number;
  /** Missing */
  missing: number;
  /** Health Percentage */
  health_percentage: number;
  /** Results */
  results: PortValidationResultModel[];
  /** Swap Recommendations */
  swap_recommendations: string[];
  /**
   * Rail Violations
   * @default []
   */
  rail_violations?: RailViolationModel[];
  /**
   * Has Rail Contamination
   * @default false
   */
  has_rail_contamination?: boolean;
  /**
   * Su Violations
   * @default []
   */
  su_violations?: SUBoundaryViolationModel[];
  /**
   * Has Su Contamination
   * @default false
   */
  has_su_contamination?: boolean;
}

/** ChatMessage */
export interface ChatMessage {
  /**
   * Role
   * The role of the message sender ('user' or 'assistant')
   */
  role: string;
  /**
   * Content
   * The content of the message
   */
  content: string;
}

/** Chunk */
export interface Chunk {
  /** Id */
  id: string;
  /** Documentid */
  documentId: string;
  /** Content */
  content: string;
  /** Metadata */
  metadata: Record<string, any>;
  /** Score */
  score: number;
  /** Source Index */
  source_index?: string | null;
  /** Image Embedding */
  image_embedding?: number[] | null;
  /** Text Embedding */
  text_embedding?: number[] | null;
}

/**
 * ClusterStatus
 * Cluster health metrics.
 */
export interface ClusterStatus {
  /** Total Nodes */
  total_nodes: number;
  /** Ready Nodes */
  ready_nodes: number;
  /** Total Gpus */
  total_gpus: number;
  /** Control Plane Ip */
  control_plane_ip: string;
}

/** ColorLegendEntry */
export interface ColorLegendEntry {
  /** Color */
  color: string;
  /** Connectiontype */
  connectionType: string;
  /** Bandwidth */
  bandwidth: string;
}

/** CompanyNamespacesResponse */
export interface CompanyNamespacesResponse {
  /** Namespaces */
  namespaces: NamespaceInfo[];
}

/** Connection */
export interface Connection {
  /** Connectionid */
  connectionId: string;
  /** Sourcedevice */
  sourceDevice: string;
  /** Sourceport */
  sourcePort: string;
  /** Destinationdevice */
  destinationDevice: string;
  /** Destinationport */
  destinationPort: string;
  /** Connectiontype */
  connectionType: string;
  /** Bandwidth */
  bandwidth: string;
  /** Istrunk */
  isTrunk: boolean;
  /** Trunksize */
  trunkSize: number | null;
  /**
   * Segment
   * @default "UNKNOWN"
   */
  segment?: "BACKEND_FABRIC" | "FRONTEND_FABRIC" | "OOB_MANAGEMENT" | "UNKNOWN" | null;
  /** Network Purpose */
  network_purpose?: string | null;
  source_port_info?: PortInfo | null;
  dest_port_info?: PortInfo | null;
  /**
   * Validation Status
   * @default "compliant"
   */
  validation_status?: string | null;
}

/**
 * ConstraintCreate
 * Request model for creating a new constraint
 */
export interface ConstraintCreate {
  /**
   * Domain
   * Domain (e.g., 'dcdc', 'network', 'security')
   */
  domain: string;
  /**
   * Category
   * Category (e.g., 'safety', 'compliance', 'workflow')
   */
  category: string;
  /**
   * Severity
   * Severity level: 'critical', 'warning', or 'info'
   */
  severity: string;
  /**
   * Rule
   * The constraint rule text
   * @minLength 1
   */
  rule: string;
  /**
   * Reasoning
   * Why this constraint exists
   * @default ""
   */
  reasoning?: string;
  /**
   * Source
   * Source or reference (e.g., 'OSHA 1910.333')
   * @default ""
   */
  source?: string;
  /**
   * Context
   * Additional context metadata
   */
  context?: Record<string, any> | null;
  /**
   * Active
   * Whether constraint is active
   * @default true
   */
  active?: boolean;
}

/**
 * ConstraintListResponse
 * Response model for list of constraints
 */
export interface ConstraintListResponse {
  /** Constraints */
  constraints: ConstraintResponse[];
  /** Total */
  total: number;
}

/**
 * ConstraintResponse
 * Response model for a single constraint
 */
export interface ConstraintResponse {
  /** Id */
  id: string;
  /** Userid */
  userId: string;
  /** Domain */
  domain: string;
  /** Category */
  category: string;
  /** Severity */
  severity: string;
  /** Rule */
  rule: string;
  /** Reasoning */
  reasoning: string;
  /** Source */
  source: string;
  /** Context */
  context?: Record<string, any> | null;
  /** Active */
  active: boolean;
  /** Createdat */
  createdAt: string;
  /** Updatedat */
  updatedAt: string;
}

/**
 * ConstraintUpdate
 * Request model for updating a constraint
 */
export interface ConstraintUpdate {
  /** Domain */
  domain?: string | null;
  /** Category */
  category?: string | null;
  /** Severity */
  severity?: string | null;
  /** Rule */
  rule?: string | null;
  /** Reasoning */
  reasoning?: string | null;
  /** Source */
  source?: string | null;
  /** Context */
  context?: Record<string, any> | null;
  /** Active */
  active?: boolean | null;
}

/**
 * CreateCustomerRequest
 * Request to create a new customer.
 */
export interface CreateCustomerRequest {
  /** Company Name */
  company_name: string;
  /**
   * Admin Email
   * @format email
   */
  admin_email: string;
  /**
   * License Tier
   * @default "starter"
   */
  license_tier?: string;
  /** Metadata */
  metadata?: Record<string, any> | null;
}

/** CreateExpertTipEntryRequest */
export interface CreateExpertTipEntryRequest {
  /** Title */
  title: string;
  /** Description */
  description: string;
  /**
   * Mediaurls
   * @default []
   */
  mediaUrls?: string[];
  /**
   * Target Index
   * @default "expert"
   */
  target_index?: string;
}

/**
 * CustomerResponse
 * Customer data response.
 */
export interface CustomerResponse {
  /** Customer Id */
  customer_id: string;
  /** Company Name */
  company_name: string;
  /** Admin Email */
  admin_email: string;
  /** License Tier */
  license_tier: string;
  /** Max Gpus */
  max_gpus: number;
  /** Max Users */
  max_users: number;
  /** Price Monthly */
  price_monthly: number;
  /** Features */
  features: string[];
  /** Status */
  status: string;
  /** Created At */
  created_at: string;
  /** Updated At */
  updated_at: string;
  /** Metadata */
  metadata: Record<string, any>;
  /** Trial Ends At */
  trial_ends_at?: string | null;
}

/**
 * DHCPDiscoverRequest
 * DHCP DISCOVER webhook payload from DHCP server
 */
export interface DHCPDiscoverRequest {
  /** Mac */
  mac: string;
  /** Remote Id */
  remote_id?: string | null;
  /** Relay Agent Ip */
  relay_agent_ip?: string | null;
  /** Hostname */
  hostname?: string | null;
}

/**
 * DHCPDiscoverResponse
 * Response to DHCP server indicating whether to assign IP
 */
export interface DHCPDiscoverResponse {
  /** Status */
  status: string;
  /** Device Name */
  device_name?: string | null;
  /** Assigned Ip */
  assigned_ip?: string | null;
  /** Location */
  location?: string | null;
  /** Alert Id */
  alert_id?: string | null;
  /** Reason */
  reason?: string | null;
  /** Expected Serial */
  expected_serial?: string | null;
  /** Detected Serial */
  detected_serial?: string | null;
}

/** DeleteHistoricRecordResponse */
export interface DeleteHistoricRecordResponse {
  /** Success */
  success: boolean;
  /** Message */
  message: string;
}

/** DeleteSessionRequest */
export interface DeleteSessionRequest {
  /** Sessionid */
  sessionId: string;
  /**
   * Target Index
   * @default "troubleshooting-sessions"
   */
  target_index?: string | null;
}

/** DeleteSessionResponse */
export interface DeleteSessionResponse {
  /** Message */
  message: string;
  /** Pinecone Vector Id */
  pinecone_vector_id: string;
}

/** DeploymentTemplate */
export interface DeploymentTemplate {
  /** Id */
  id: string;
  /** Name */
  name: string;
  /** Description */
  description: string;
  /** Gpu Count */
  gpu_count?: number | null;
  /** Node Count */
  node_count?: number | null;
  /** Su Count */
  su_count?: number | null;
  /** Leaf Switches */
  leaf_switches?: number | null;
  /** Spine Switches */
  spine_switches?: number | null;
  /** Topology */
  topology: string;
  /** Fabric */
  fabric: string;
  /** Bandwidth */
  bandwidth: string;
  /** Use Cases */
  use_cases: string[];
  /** Icon */
  icon: string;
}

/** Device */
export interface Device {
  /** Deviceid */
  deviceId: string;
  /** Devicename */
  deviceName: string;
  /** Devicetype */
  deviceType: string;
  /** Racklocation */
  rackLocation: string;
  /** Position */
  position: Record<string, any>;
  /** Ports */
  ports: Record<string, any>[];
  /** Metadata */
  metadata: Record<string, any>;
  location?: LocationInfo | null;
  hardware_info?: HardwareInfo | null;
  network_metadata?: NetworkMetadata | null;
  /**
   * Verification Status
   * @default "pending"
   */
  verification_status?: string | null;
}

/** DeviceConventions */
export interface DeviceConventions {
  /** Computeprefix */
  computePrefix: string;
  /** Storageprefix */
  storagePrefix: string;
  /** Switchleafprefix */
  switchLeafPrefix: string;
  /** Switchspineprefix */
  switchSpinePrefix: string;
}

/**
 * DirectApproveRequest
 * Request model for direct user approval
 */
export interface DirectApproveRequest {
  /** Uid */
  uid: string;
  /** Approved */
  approved: boolean;
  /** Rejection Reason */
  rejection_reason?: string;
}

/** DirectRegistrationRequest */
export interface DirectRegistrationRequest {
  /** Email */
  email: string;
  /** Password */
  password: string;
  /** Displayname */
  displayName: string;
  /**
   * Role
   * @default "technician"
   */
  role?: string;
  /** Company */
  company?: string | null;
  /** Location */
  location?: string | null;
  /**
   * Force Recreate
   * @default false
   */
  force_recreate?: boolean;
}

/** DirectRegistrationResponse */
export interface DirectRegistrationResponse {
  /** Success */
  success: boolean;
  /** Userid */
  userId?: string | null;
  /** Message */
  message: string;
}

/**
 * DiscoveryReport
 * Switch identity report from discovery script.
 */
export interface DiscoveryReport {
  /** Mac */
  mac: string;
  /** Serial */
  serial: string;
  /** Vendor */
  vendor?: string | null;
  /** Model */
  model?: string | null;
  /** Switch Id */
  switch_id?: string | null;
}

/**
 * DiscoveryResponse
 * Response to discovery callback.
 */
export interface DiscoveryResponse {
  /** Status */
  status: string;
  /** Message */
  message: string;
  /** Next Step */
  next_step: string;
  /** Device Name */
  device_name?: string | null;
  /** Assigned Ip */
  assigned_ip?: string | null;
  /** Alert Id */
  alert_id?: string | null;
}

/** DocumentListResponse */
export interface DocumentListResponse {
  /** Documents */
  documents: DocumentResponse[];
  /** Pagination */
  pagination: Record<string, any>;
  /** Message */
  message?: string | null;
  /** Error */
  error?: string | null;
}

/** DocumentMetricsSummary */
export interface DocumentMetricsSummary {
  /** Document Count */
  document_count: number;
}

/** DocumentResponse */
export interface DocumentResponse {
  /** Id */
  id: string;
  /** Title */
  title: string;
  /** Filename */
  fileName: string;
  /** Filetype */
  fileType: string;
  /** Status */
  status: string;
  /** Company */
  company: string;
  /** Createdat */
  createdAt: string;
  /** Source */
  source: string;
  /** Jobid */
  jobId?: string | null;
  /** Description */
  description?: string | null;
  /**
   * Isprocessed
   * @default false
   */
  isProcessed?: boolean;
  /**
   * Tags
   * @default []
   */
  tags?: string[];
  /** Organization */
  organization?: string | null;
  /** Filesize */
  fileSize?: number | null;
  /** Totalchunks */
  totalChunks?: number | null;
  progress?: ProcessingProgress | null;
  /** Target Index */
  target_index?: string | null;
}

/** DocumentStatus */
export interface DocumentStatus {
  /** Status */
  status: string;
  progress?: ProcessingProgress | null;
  /** Error */
  error?: string | null;
}

/** DocumentUpdateRequest */
export interface DocumentUpdateRequest {
  /**
   * Title
   * Document title
   */
  title?: string | null;
  /**
   * Description
   * Document description
   */
  description?: string | null;
  /**
   * Tags
   * Tags for categorization
   */
  tags?: string[] | null;
  /**
   * Status
   * Document status
   */
  status?: string | null;
}

/** DomainListResponse */
export interface DomainListResponse {
  /** Domains */
  domains: Record<string, string>;
}

/** EmailRequest */
export interface EmailRequest {
  /**
   * To
   * @format email
   */
  to: string;
  /** Subject */
  subject: string;
  /** Content Text */
  content_text: string;
  /** Content Html */
  content_html?: string | null;
}

/** EmailResponse */
export interface EmailResponse {
  /** Success */
  success: boolean;
  /** Message */
  message: string;
}

/** EmergencyOverrideRequest */
export interface EmergencyOverrideRequest {
  /** Device Name */
  device_name: string;
  /** Override Token */
  override_token: string;
  /** Reason */
  reason: string;
}

/** ExpertKnowledgeRequest */
export interface ExpertKnowledgeRequest {
  /** Entryid */
  entryId: string;
  /** Problem */
  problem: string;
  /** Solution */
  solution: string;
  /** Tags */
  tags: string[];
  /**
   * Target Index
   * @default "expert"
   */
  target_index?: string | null;
}

/** ExpertTipRequest */
export interface ExpertTipRequest {
  /** Document Id */
  document_id: string;
}

/** ExtractionResultsResponse */
export interface ExtractionResultsResponse {
  /** Devices */
  devices: Device[];
  /** Connections */
  connections: Connection[];
}

/** FeedbackTranscriptionRequest */
export interface FeedbackTranscriptionRequest {
  /**
   * Feedback Id
   * The ID of the feedback to transcribe
   */
  feedback_id: string;
  /**
   * Audio Data
   * Base64 encoded audio data
   */
  audio_data: string;
}

/** FeedbackTranscriptionResponse */
export interface FeedbackTranscriptionResponse {
  /**
   * Feedback Id
   * The ID of the feedback that was transcribed
   */
  feedback_id: string;
  /**
   * Transcript
   * The transcribed feedback
   */
  transcript: string;
}

/** FileUploadResponse */
export interface FileUploadResponse {
  /** Message */
  message: string;
  /** Gcs Path */
  gcs_path: string;
  /** Filename */
  filename: string;
  /** Session Id */
  session_id: string;
}

/** FirebaseStatusResponse */
export interface FirebaseStatusResponse {
  /** Initialized */
  initialized: boolean;
  /** Message */
  message: string;
  /** Project Id */
  project_id?: string | null;
  /** Default App Name */
  default_app_name?: string | null;
}

/** GeneralFileUploadResponse */
export interface GeneralFileUploadResponse {
  /** Gcs Path */
  gcs_path: string;
  /** Filename */
  filename: string;
}

/** GenerateConfigRequest */
export interface GenerateConfigRequest {
  topology: TopologyConfig;
  /** Devices */
  devices: BomDevice[];
}

/** HTTPValidationError */
export interface HTTPValidationError {
  /** Detail */
  detail?: ValidationError[];
}

/**
 * HardwareInfo
 * Hardware details from asset inventory CSV
 */
export interface HardwareInfo {
  /** Manufacturer */
  manufacturer?: string | null;
  /** Model */
  model?: string | null;
  /** Form Factor */
  form_factor?: string | null;
  /** Serial Number */
  serial_number?: string | null;
  /** Asset Tag */
  asset_tag?: string | null;
  /** Mac Address */
  mac_address?: string | null;
  /** Purchase Date */
  purchase_date?: string | null;
  /** Warranty Expiry */
  warranty_expiry?: string | null;
}

/** HealthResponse */
export interface HealthResponse {
  /** Status */
  status: string;
}

/**
 * ImportTemplatesRequest
 * Request model for importing constraint templates
 */
export interface ImportTemplatesRequest {
  /**
   * Domain
   * Domain to assign to imported constraints
   */
  domain: string;
  /**
   * Templateset
   * Template set to import (currently only 'dcdc')
   * @default "dcdc"
   */
  templateSet?: string;
  /**
   * Skipduplicates
   * Skip templates with duplicate rule text
   * @default true
   */
  skipDuplicates?: boolean;
}

/**
 * ImportTemplatesResponse
 * Response model for template import
 */
export interface ImportTemplatesResponse {
  /** Imported */
  imported: number;
  /** Skipped */
  skipped: number;
  /** Message */
  message: string;
}

/**
 * JoinNodeRequest
 * Request to join worker node to cluster.
 */
export interface JoinNodeRequest {
  /** Node Ip */
  node_ip: string;
  /** Node Hostname */
  node_hostname: string;
  /**
   * Tier
   * @default "COMPUTE"
   */
  tier?: string;
  /**
   * Gpu Count
   * @default 8
   */
  gpu_count?: number;
}

/**
 * JoinNodeResponse
 * Worker node join result.
 */
export interface JoinNodeResponse {
  /** Status */
  status: string;
  /** Node Hostname */
  node_hostname: string;
  /** Node Ip */
  node_ip?: string | null;
  /** Message */
  message?: string | null;
  /** Error */
  error?: string | null;
}

/**
 * LLDPNeighbor
 * LLDP neighbor information from switch.
 */
export interface LLDPNeighbor {
  /** Port Id */
  port_id: string;
  /** Neighbor Hostname */
  neighbor_hostname: string;
  /** Neighbor Description */
  neighbor_description?: string | null;
  /** Neighbor Mac */
  neighbor_mac?: string | null;
}

/**
 * LocationInfo
 * 5-level hierarchical location (DCIM standard)
 */
export interface LocationInfo {
  /** Site */
  site?: string | null;
  /** Room */
  room?: string | null;
  /** Row */
  row?: string | null;
  /** Rack */
  rack?: string | null;
  /** U Position */
  u_position?: string | null;
}

/**
 * MergeValidationResponse
 * Response model for merge validation
 */
export interface MergeValidationResponse {
  /** Project Id */
  projectId: string;
  /** Total Devices */
  total_devices: number;
  /** Verified Count */
  verified_count: number;
  /** Pending Count */
  pending_count: number;
  /** Devices */
  devices: Record<string, any>[];
}

/** NamespaceInfo */
export interface NamespaceInfo {
  /** Id */
  id: string;
  /** Displayname */
  displayName: string;
  /**
   * Isdefault
   * @default false
   */
  isDefault?: boolean;
}

/**
 * NetworkMetadata
 * Network-specific metadata for switches and network devices
 */
export interface NetworkMetadata {
  /** Tier */
  tier: "BACKEND_FABRIC" | "FRONTEND_FABRIC" | "OOB_MANAGEMENT" | "UNKNOWN";
  /** Protocol */
  protocol?: string | null;
  /** Link Speed Capability */
  link_speed_capability?: string | null;
  /** Fabric Type */
  fabric_type?: string | null;
  /** Port Count Detected */
  port_count_detected?: number | null;
  /** Connector Type */
  connector_type?: string | null;
  /** Switch Role */
  switch_role?: string | null;
  /** Confidence Score */
  confidence_score?: number | null;
  /** Evidence */
  evidence?: string | null;
}

/**
 * NodeInfo
 * K8s node details with GPU info.
 */
export interface NodeInfo {
  /** Name */
  name: string;
  /** Status */
  status: string;
  /** Ip */
  ip: string;
  /** Tier */
  tier: string;
  /** Gpu Count */
  gpu_count: number;
  /** Cpu Cores */
  cpu_cores: number;
  /** Memory Gb */
  memory_gb: number;
  /** Created At */
  created_at: string;
  /** Provisioned By */
  provisioned_by: string;
}

/**
 * NodeTopologyResponse
 * Topology information for a single node.
 */
export interface NodeTopologyResponse {
  /** Node Name */
  node_name: string;
  /** Su Id */
  su_id: string | null;
  /** Rack Id */
  rack_id: string | null;
  /** Rail Id */
  rail_id: string | null;
  /** Roce Ready */
  roce_ready: boolean;
  /** Zone */
  zone: string | null;
  /** Region */
  region: string | null;
}

/** PendingUser */
export interface PendingUser {
  /**
   * Id
   * Firestore document ID for this request
   */
  id: string;
  /**
   * Uid
   * User ID in Firebase Auth (same as document ID)
   */
  uid: string;
  /** Useremail */
  userEmail: string;
  /** Displayname */
  displayName: string;
  /** Requestedrole */
  requestedRole: string;
  /** Company */
  company?: string | null;
  /** Requestedat */
  requestedAt?: Record<string, number> | null;
  /** Status */
  status: string;
  /** Reviewedby */
  reviewedBy?: string | null;
  /** Reviewedat */
  reviewedAt?: Record<string, number> | null;
  /** Rejectionreason */
  rejectionReason?: string | null;
}

/**
 * PendingUserListResponse
 * Response model for pending user requests.
 * Note: The 'id' and 'uid' fields should be identical - both contain the Firebase Auth user ID.
 */
export interface PendingUserListResponse {
  /** Users */
  users: PendingUser[];
  /** Total */
  total: number;
}

/**
 * PortInfo
 * Enhanced port information
 */
export interface PortInfo {
  /** Port Label */
  port_label: string;
  /** Port Type */
  port_type?: string | null;
}

/**
 * PortValidationResultModel
 * Validation result for a single port.
 */
export interface PortValidationResultModel {
  /** Port Id */
  port_id: string;
  /** Port Number */
  port_number: number;
  /** Status */
  status: string;
  /** Expected Neighbor */
  expected_neighbor: string | null;
  /** Actual Neighbor */
  actual_neighbor: string | null;
  /** Mismatch Details */
  mismatch_details?: string | null;
  /** Swap Recommendation */
  swap_recommendation?: string | null;
}

/** ProcessingConfig */
export interface ProcessingConfig {
  /** Autoexpandtrunks */
  autoExpandTrunks: boolean;
  /** Validaterailalignment */
  validateRailAlignment: boolean;
  /** Spotchecksamplesize */
  spotCheckSampleSize: number;
}

/** ProcessingProgress */
export interface ProcessingProgress {
  /** Stage */
  stage: string;
  /** Progress */
  progress: number;
  /** Message */
  message: string;
  /** Lastupdated */
  lastUpdated?: string | null;
}

/** ProcessingStatusResponse */
export interface ProcessingStatusResponse {
  /** Project Id */
  projectId: string;
  /** Status */
  status: string;
  /** Progress Percentage */
  progress_percentage: number;
  /** Current Stage */
  current_stage: string;
  /** Error Message */
  error_message: string | null;
}

/**
 * ProjectListResponse
 * Response model for listing cluster bringup projects
 */
export interface ProjectListResponse {
  /** Projects */
  projects: Record<string, any>[];
}

/**
 * ProvisioningAlert
 * Alert for Installation Lead dashboard
 */
export interface ProvisioningAlert {
  /** Alert Id */
  alert_id: string;
  /** Project Id */
  projectId: string;
  /** Severity */
  severity: string;
  /** Type */
  type: string;
  /** Status */
  status: string;
  /** Location */
  location?: Record<string, any> | null;
  /** Planned */
  planned?: Record<string, any> | null;
  /** Detected */
  detected?: Record<string, any> | null;
  /** Message */
  message: string;
  /** Impact */
  impact: string;
  /** Recommendation */
  recommendation: string;
  /** Created At */
  created_at: string;
  /** Resolved At */
  resolved_at?: string | null;
  /** Resolved By */
  resolved_by?: string | null;
  /** Resolution Action */
  resolution_action?: string | null;
}

/**
 * QuotaResponse
 * GPU quota usage response.
 */
export interface QuotaResponse {
  /** Max Gpus */
  max_gpus: number;
  /** Used Gpus */
  used_gpus: number;
  /** Remaining Gpus */
  remaining_gpus: number;
  /** Quota Exceeded */
  quota_exceeded: boolean;
  /** License Tier */
  license_tier: string;
}

/**
 * RailViolationModel
 * Rail isolation violation for cross-plane cabling.
 */
export interface RailViolationModel {
  /** Port Id */
  port_id: string;
  /** Expected Plane */
  expected_plane: number;
  /** Actual Tail */
  actual_tail: number | null;
  /** Neighbor Hostname */
  neighbor_hostname: string;
  /** Severity */
  severity: string;
  /** Violation Type */
  violation_type: string;
  /** Impact */
  impact: string;
  /** Action */
  action: string;
}

/**
 * ReportGenerationRequest
 * The frontend only needs to send the session_id and any last-minute notes from the technician.
 */
export interface ReportGenerationRequest {
  /** Session Id */
  session_id: string;
  /**
   * Technician Final Notes
   * Optional final voice or text notes from the technician.
   */
  technician_final_notes?: string | null;
}

/** ReportGenerationResponse */
export interface ReportGenerationResponse {
  /** Generated Report Markdown */
  generated_report_markdown: string;
}

/** ReportGetResponse */
export interface ReportGetResponse {
  /** Report Id */
  report_id: string;
  /** Session Id */
  session_id: string;
  /** Technician Uid */
  technician_uid: string;
  /** Company */
  company: string;
  /**
   * Created At
   * @format date-time
   */
  created_at: string;
  /** Location */
  location: string;
  /** Report Markdown */
  report_markdown: string;
}

/** ReportSaveRequest */
export interface ReportSaveRequest {
  /** Session Id */
  session_id: string;
  /** Report Markdown */
  report_markdown: string;
}

/** ReportSaveResponse */
export interface ReportSaveResponse {
  /** Success */
  success: boolean;
  /** Report Id */
  report_id: string;
}

/** ReprocessRequest */
export interface ReprocessRequest {
  /** Document Id */
  document_id: string;
}

/** ReprocessResponse */
export interface ReprocessResponse {
  /** Message */
  message: string;
  /** Document Id */
  document_id: string;
}

/**
 * ResolveAlertRequest
 * Installation Lead's resolution action
 */
export interface ResolveAlertRequest {
  /** Alert Id */
  alert_id: string;
  /** Strategy */
  strategy: string;
  /** Resolved By */
  resolved_by: string;
}

/** ResolveAlertResponse */
export interface ResolveAlertResponse {
  /** Status */
  status: string;
  /** Message */
  message: string;
}

/** ResponseData */
export interface ResponseData {
  /**
   * Text Response
   * The AI-generated text response
   */
  text_response: string;
  /**
   * Audio Url
   * URL to the generated audio response
   */
  audio_url?: string | null;
  /**
   * User Has Submitted Feedback
   * Indicates if user submitted feedback for this session
   * @default false
   */
  user_has_submitted_feedback?: boolean;
  /**
   * Status
   * Overall status of the response generation
   * @default "success"
   */
  status?: string;
  /**
   * Notes
   * Additional notes or error details
   */
  notes?: string | null;
  /**
   * Knowledge Sources Used
   * Knowledge base sources used
   */
  knowledge_sources_used?: Record<string, any>[] | null;
  /**
   * Web Sources Used
   * Web sources used
   */
  web_sources_used?: Record<string, any>[] | null;
}

/** ResponseRequest */
export interface ResponseRequest {
  /**
   * Session Id
   * The ID of the troubleshooting session
   */
  session_id: string;
  /**
   * Transcript
   * The transcribed voice command
   */
  transcript: string;
  /**
   * Uid
   * The ID of the user requesting the response
   */
  uid: string;
  /**
   * Command Id
   * The ID of the user's command document in Firestore
   */
  command_id: string;
  /**
   * History
   * The conversation history
   */
  history?: ChatMessage[] | null;
  /**
   * Media Urls
   * GCS URLs of any media files
   */
  media_urls?: string[] | null;
  /**
   * Session Organization
   * Organization from the current session
   */
  session_organization?: string | null;
  /**
   * Use Knowledge Base
   * Whether to use the knowledge base for RAG
   * @default true
   */
  use_knowledge_base?: boolean | null;
  /**
   * Use Web Search
   * Whether to use web search
   * @default true
   */
  use_web_search?: boolean | null;
}

/** RetrievalRequest */
export interface RetrievalRequest {
  /** Query */
  query: string;
  /** Company */
  company: string;
  /**
   * Max Results
   * @default 5
   */
  max_results?: number;
  /** Score Threshold */
  score_threshold?: number | null;
  /** Media Urls */
  media_urls?: string[] | null;
  /** Namespaces */
  namespaces?: string[] | null;
}

/** RetrievalResponse */
export interface RetrievalResponse {
  /**
   * Chunks
   * Retrieved document chunks
   */
  chunks: Chunk[];
  /**
   * Query
   * Original query
   */
  query: string;
}

/**
 * SUBoundaryViolationModel
 * SU boundary violation for cross-SU cabling.
 *
 * This represents a CRITICAL systemic deployment error where a switch
 * meant for one Scalable Unit is cabled to devices in another SU.
 * Unlike rail violations (localized mis-wires), SU breaches indicate
 * wrong rack placement or switch role confusion.
 */
export interface SUBoundaryViolationModel {
  /** Port Id */
  port_id: string;
  /** Neighbor Hostname */
  neighbor_hostname: string;
  /** Expected Su Id */
  expected_su_id: number;
  /** Actual Su Id */
  actual_su_id: number;
  /**
   * Severity
   * @default "CRITICAL"
   */
  severity?: string;
  /** Violation Type */
  violation_type: string;
  /** Impact */
  impact: string;
  /** Action */
  action: string;
}

/** SchematicConfigRequest */
export interface SchematicConfigRequest {
  /** Project Id */
  projectId: string;
  /** Color Legend */
  color_legend: ColorLegendEntry[];
  device_conventions: DeviceConventions;
  processing_config: ProcessingConfig;
}

/** SchematicUploadResponse */
export interface SchematicUploadResponse {
  /** Project Id */
  projectId: string;
  /** Schematic Url */
  schematic_url: string;
  /** Status */
  status: string;
}

/**
 * SecureMediaUrlsResponse
 * Response model containing a list of secure, signed URLs for media files.
 */
export interface SecureMediaUrlsResponse {
  /** Secure Urls */
  secure_urls: string[];
}

/** SecureUrlResponse */
export interface SecureUrlResponse {
  /** Signed Url */
  signed_url: string;
}

/**
 * SuspendCustomerRequest
 * Request to suspend customer.
 */
export interface SuspendCustomerRequest {
  /**
   * Reason
   * @default "Payment failure"
   */
  reason?: string;
}

/**
 * SyncTopologyResponse
 * Response from topology sync operation.
 */
export interface SyncTopologyResponse {
  /** Synced Count */
  synced_count: number;
  /** Failed Count */
  failed_count: number;
  /** Total Nodes */
  total_nodes: number;
  /** Errors */
  errors: string[];
  /** Synced Nodes */
  synced_nodes: string[];
  /** Success */
  success: boolean;
}

/** SynthesisRequest */
export interface SynthesisRequest {
  /** Text */
  text: string;
}

/** SynthesisResponse */
export interface SynthesisResponse {
  /** Audio Url */
  audio_url: string;
}

/**
 * TemplateMetadata
 * Metadata about a template set
 */
export interface TemplateMetadata {
  /** Name */
  name: string;
  /** Description */
  description: string;
  /** Count */
  count: number;
  /** Categories */
  categories: string[];
  /** Domain */
  domain: string;
  /** Version */
  version: string;
}

/** TopologyConfig */
export interface TopologyConfig {
  /** Template Id */
  template_id: string;
  /** Su Count */
  su_count: number;
  /** Nodes Per Su */
  nodes_per_su: number;
  /** Gpus Per Node */
  gpus_per_node: number;
  /** Leaf Switches Per Su */
  leaf_switches_per_su: number;
  /** Spine Switches */
  spine_switches: number;
  /** Ip Base */
  ip_base: string;
  /** Vlan Base */
  vlan_base: number;
  /** Company Name */
  company_name: string;
  /** Customer Id */
  customer_id: string;
}

/** TranscriptionResponse */
export interface TranscriptionResponse {
  /** Transcription */
  transcription: string;
}

/**
 * UpdateCustomerRequest
 * Request to update customer data.
 */
export interface UpdateCustomerRequest {
  /** Company Name */
  company_name?: string | null;
  /** Status */
  status?: string | null;
  /** Metadata */
  metadata?: Record<string, any> | null;
}

/**
 * UpgradeLicenseRequest
 * Request to upgrade license tier.
 */
export interface UpgradeLicenseRequest {
  /** New Tier */
  new_tier: string;
}

/** UserData */
export interface UserData {
  /** Id */
  id: string;
  /** Uid */
  uid: string;
  /** Email */
  email: string;
  /** Displayname */
  displayName?: string | null;
  /** Role */
  role?: string | null;
  /** Company */
  company?: string | null;
  /** Status */
  status?: string | null;
  /** Approvalstatus */
  approvalStatus?: string | null;
  /** Assigneddomain */
  assignedDomain?: string | null;
  /** Createdat */
  createdAt?: string | null;
  /** Lastactive */
  lastActive?: string | null;
  /** Approvedat */
  approvedAt?: string | null;
  /** Rejectedat */
  rejectedAt?: string | null;
  /** Approvedby */
  approvedBy?: string | null;
  /** Rejectedby */
  rejectedBy?: string | null;
  /** Rejectionreason */
  rejectionReason?: string | null;
  /** Photourl */
  photoURL?: string | null;
}

/** UserListResponse */
export interface UserListResponse {
  /** Users */
  users: UserData[];
  /** Total */
  total: number;
}

/** UserRegistrationRequest */
export interface UserRegistrationRequest {
  /** Email */
  email: string;
  /** Password */
  password: string;
  /** Displayname */
  displayName: string;
  /** Role */
  role: string;
  /** Company */
  company?: string | null;
  /** Location */
  location?: string | null;
  /** Organization */
  organization?: string | null;
}

/** UserRegistrationResponse */
export interface UserRegistrationResponse {
  /** Success */
  success: boolean;
  /** Userid */
  userId?: string | null;
  /** Message */
  message: string;
  /**
   * Approvalstatus
   * @default "pending_approval"
   */
  approvalStatus?: string;
}

/** ValidationError */
export interface ValidationError {
  /** Location */
  loc: (string | number)[];
  /** Message */
  msg: string;
  /** Error Type */
  type: string;
}

/**
 * VerifySyncResponse
 * Health check response for topology sync status.
 */
export interface VerifySyncResponse {
  /** Total Nodes */
  total_nodes: number;
  /** Labeled Nodes */
  labeled_nodes: number;
  /** Unlabeled Nodes */
  unlabeled_nodes: number;
  /** Unlabeled Node Names */
  unlabeled_node_names: string[];
  /** Sync Health */
  sync_health: string;
}

/** WebSearchRequest */
export interface WebSearchRequest {
  /**
   * Query
   * The query to search for on the web
   */
  query: string;
  /**
   * Search Depth
   * Search depth (basic, advanced)
   * @default "advanced"
   */
  search_depth?: string;
  /**
   * Max Results
   * Maximum number of results to return
   * @default 5
   */
  max_results?: number;
  /**
   * Include Domains
   * Domains to specifically include in search
   */
  include_domains?: string[] | null;
  /**
   * Exclude Domains
   * Domains to exclude from search
   */
  exclude_domains?: string[] | null;
}

/** WebSearchResponse */
export interface WebSearchResponse {
  /**
   * Results
   * List of search results
   */
  results: WebSearchResult[];
  /**
   * Query
   * Original query
   */
  query: string;
  /**
   * Query Id
   * Unique ID for this query
   */
  query_id: string;
  /**
   * Company Context
   * Company context used for search, if any
   */
  company_context?: string | null;
}

/** WebSearchResult */
export interface WebSearchResult {
  /**
   * Title
   * Title of the search result
   */
  title: string;
  /**
   * Url
   * URL of the search result
   */
  url: string;
  /**
   * Content
   * Content snippet from the search result
   */
  content: string;
  /**
   * Score
   * Relevance score
   */
  score: number;
  /**
   * Source
   * Source domain
   */
  source: string;
}

/** WorkerPayload */
export interface WorkerPayload {
  /** Doc Id */
  doc_id: string;
  /** File Url */
  file_url: string;
  /** Doc Data */
  doc_data: Record<string, any>;
  /** Is Sub Document */
  is_sub_document: boolean;
  /** Original Doc Id */
  original_doc_id: string;
  /**
   * Target Index
   * @default "general"
   */
  target_index?: string | null;
  /** Start Page Original */
  start_page_original: number;
}

/**
 * ZTPCompletionRequest
 * ZTP completion webhook payload.
 */
export interface ZTPCompletionRequest {
  /** Node Hostname */
  node_hostname: string;
  /** Node Ip */
  node_ip: string;
  /** Mac Address */
  mac_address: string;
  /** Ztp Status */
  ztp_status: string;
  /** Error */
  error?: string | null;
}

/**
 * ZTPCompletionResponse
 * ZTP completion webhook response.
 */
export interface ZTPCompletionResponse {
  /** Status */
  status: string;
  /** Message */
  message: string;
  /** K8S Join Status */
  k8s_join_status?: string | null;
}

/** ZipUploadResponse */
export interface ZipUploadResponse {
  /** Message */
  message: string;
  /** Job Id */
  job_id: string;
  /** Documents */
  documents: DocumentResponse[];
}

export type CheckHealthData = HealthResponse;

export type AddSessionToKnowledgeBaseData = any;

export type AddSessionToKnowledgeBaseError = HTTPValidationError;

export type AddExpertEntryToKnowledgeBaseData = AddEntryResponse;

export type AddExpertEntryToKnowledgeBaseError = HTTPValidationError;

export type DeleteSessionFromKnowledgeBaseData = DeleteSessionResponse;

export type DeleteSessionFromKnowledgeBaseError = HTTPValidationError;

export type ApproveExpertTipData = any;

export type ApproveExpertTipError = HTTPValidationError;

export type RejectExpertTipData = any;

export type RejectExpertTipError = HTTPValidationError;

export type DeleteExpertTipFromKnowledgeBaseData = any;

export type DeleteExpertTipFromKnowledgeBaseError = HTTPValidationError;

export interface StreamAudioFileParams {
  /** Filename */
  filename: string;
}

export type StreamAudioFileData = any;

export type StreamAudioFileError = HTTPValidationError;

export type TranscribeAudioData = TranscriptionResponse;

export type TranscribeAudioError = HTTPValidationError;

export type TranscribeAudioOptionsData = any;

export type UploadZipArchiveData = ZipUploadResponse;

export type UploadZipArchiveError = HTTPValidationError;

export type UploadGeneralFileData = GeneralFileUploadResponse;

export type UploadGeneralFileError = HTTPValidationError;

export type SearchWebData = WebSearchResponse;

export type SearchWebError = HTTPValidationError;

export type GetCsvHeadersData = CSVHeadersResponse;

export type GetCsvHeadersError = HTTPValidationError;

export type UploadHistoricRecordsCsvData = CSVUploadResponse;

export type UploadHistoricRecordsCsvError = HTTPValidationError;

export interface DeleteHistoricRecordParams {
  /**
   * Target Index
   * @default "historic"
   */
  target_index?: string;
  /** Record Id */
  recordId: string;
}

export type DeleteHistoricRecordData = DeleteHistoricRecordResponse;

export type DeleteHistoricRecordError = HTTPValidationError;

export type BulkDeleteHistoricRecordsData = BulkDeleteHistoricRecordsResponse;

export type BulkDeleteHistoricRecordsError = HTTPValidationError;

export interface ListHistoricRecordsParams {
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
}

export type ListHistoricRecordsData = any;

export type ListHistoricRecordsError = HTTPValidationError;

export type TranscribeFeedbackData = FeedbackTranscriptionResponse;

export type TranscribeFeedbackError = HTTPValidationError;

export type SendEmailData = EmailResponse;

export type SendEmailError = HTTPValidationError;

export type GenerateResponseData = ResponseData;

export type GenerateResponseError = HTTPValidationError;

export type HandleDiscoveryCallbackData = DiscoveryResponse;

export type HandleDiscoveryCallbackError = HTTPValidationError;

export interface GetFullZtpConfigParams {
  /** Mac Address */
  macAddress: string;
}

export type GetFullZtpConfigData = any;

export type GetFullZtpConfigError = HTTPValidationError;

export interface GetDiscoveryScriptParams {
  /** Mac Address */
  macAddress: string;
}

export type GetDiscoveryScriptData = any;

export type GetDiscoveryScriptError = HTTPValidationError;

export type ValidateCablingData = CablingValidationResponse;

export type ValidateCablingError = HTTPValidationError;

export type UploadSchematicFileData = SchematicUploadResponse;

export type UploadSchematicFileError = HTTPValidationError;

export type ConfigureSchematicProcessingData = any;

export type ConfigureSchematicProcessingError = HTTPValidationError;

export interface GetProcessingStatusParams {
  /** Project Id */
  projectId: string;
}

export type GetProcessingStatusData = ProcessingStatusResponse;

export type GetProcessingStatusError = HTTPValidationError;

export interface GetExtractionResultsParams {
  /** Project Id */
  projectId: string;
}

export type GetExtractionResultsData = ExtractionResultsResponse;

export type GetExtractionResultsError = HTTPValidationError;

export interface ExportCablingMatrixParams {
  /** Project Id */
  projectId: string;
}

export type ExportCablingMatrixData = any;

export type ExportCablingMatrixError = HTTPValidationError;

export type ListProjectsData = ProjectListResponse;

export interface DeleteProjectParams {
  /** Project Id */
  projectId: string;
}

export type DeleteProjectData = any;

export type DeleteProjectError = HTTPValidationError;

export interface UploadAssetInventoryParams {
  /** Project Id */
  projectId: string;
}

export type UploadAssetInventoryData = AssetInventoryUploadResponse;

export type UploadAssetInventoryError = HTTPValidationError;

export interface GetMergeValidationParams {
  /** Project Id */
  projectId: string;
}

export type GetMergeValidationData = MergeValidationResponse;

export type GetMergeValidationError = HTTPValidationError;

export type DownloadAssetTemplateData = any;

export type DownloadTestSchematicData = any;

export type DownloadTestCsvData = any;

export interface DhcpDiscoveryWebhookParams {
  /** Project Id */
  projectId: string;
}

export type DhcpDiscoveryWebhookData = DHCPDiscoverResponse;

export type DhcpDiscoveryWebhookError = HTTPValidationError;

export interface GetProvisioningAlertsParams {
  /** Project Id */
  projectId: string;
}

/** Response Get Provisioning Alerts */
export type GetProvisioningAlertsData = ProvisioningAlert[];

export type GetProvisioningAlertsError = HTTPValidationError;

export type ResolveProvisioningAlertData = ResolveAlertResponse;

export type ResolveProvisioningAlertError = HTTPValidationError;

export interface GetProvisioningStatusParams {
  /** Project Id */
  projectId: string;
}

export type GetProvisioningStatusData = any;

export type GetProvisioningStatusError = HTTPValidationError;

export interface GetTierHealthParams {
  /** Project Id */
  projectId: string;
  /** Tier */
  tier: string;
}

export type GetTierHealthData = any;

export type GetTierHealthError = HTTPValidationError;

export interface GetClusterReadinessParams {
  /** Project Id */
  projectId: string;
}

export type GetClusterReadinessData = any;

export type GetClusterReadinessError = HTTPValidationError;

export interface EmergencyOverrideParams {
  /** Project Id */
  projectId: string;
}

export type EmergencyOverrideData = any;

export type EmergencyOverrideError = HTTPValidationError;

export interface GetIpAllocationPreviewParams {
  /** Project Id */
  projectId: string;
}

export type GetIpAllocationPreviewData = any;

export type GetIpAllocationPreviewError = HTTPValidationError;

export type RegisterUserData = UserRegistrationResponse;

export type RegisterUserError = HTTPValidationError;

export interface ListConstraintsParams {
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
}

export type ListConstraintsData = ConstraintListResponse;

export type ListConstraintsError = HTTPValidationError;

export type CreateNewConstraintData = ConstraintResponse;

export type CreateNewConstraintError = HTTPValidationError;

export interface UpdateExistingConstraintParams {
  /** Constraint Id */
  constraintId: string;
}

export type UpdateExistingConstraintData = ConstraintResponse;

export type UpdateExistingConstraintError = HTTPValidationError;

export interface DeleteExistingConstraintParams {
  /** Constraint Id */
  constraintId: string;
}

/** Response Delete Existing Constraint */
export type DeleteExistingConstraintData = Record<string, string>;

export type DeleteExistingConstraintError = HTTPValidationError;

export type ImportConstraintTemplatesData = ImportTemplatesResponse;

export type ImportConstraintTemplatesError = HTTPValidationError;

export type GetAvailableConstraintTemplatesData = AvailableTemplatesResponse;

export interface GetSecureMediaUrlsForTipParams {
  /** Tip Id */
  tipId: string;
}

export type GetSecureMediaUrlsForTipData = SecureMediaUrlsResponse;

export type GetSecureMediaUrlsForTipError = HTTPValidationError;

export type FirebaseStatusData = FirebaseStatusResponse;

export type RetrieveKnowledgeData = RetrievalResponse;

export type RetrieveKnowledgeError = HTTPValidationError;

export type GetCompanyNamespacesEndpointData = CompanyNamespacesResponse;

export interface SyncTopologyParams {
  /** Project Id */
  projectId: string;
}

export type SyncTopologyData = SyncTopologyResponse;

export type SyncTopologyError = HTTPValidationError;

export interface GetNodeTopologyParams {
  /** Node Name */
  nodeName: string;
}

export type GetNodeTopologyData = NodeTopologyResponse;

export type GetNodeTopologyError = HTTPValidationError;

export interface VerifySyncParams {
  /** Project Id */
  projectId: string;
}

export type VerifySyncData = VerifySyncResponse;

export type VerifySyncError = HTTPValidationError;

export interface SyncSingleNodeParams {
  /** Project Id */
  projectId: string;
  /** Node Name */
  nodeName: string;
}

/** Response Sync Single Node */
export type SyncSingleNodeData = Record<string, any>;

export type SyncSingleNodeError = HTTPValidationError;

export type SynthesizeData = SynthesisResponse;

export type SynthesizeError = HTTPValidationError;

export type ProcessDocumentWorkerData = any;

export type ProcessDocumentWorkerError = HTTPValidationError;

export type ValidateBomUploadData = BomValidationResponse;

export type ValidateBomUploadError = HTTPValidationError;

/** Response List Deployment Templates */
export type ListDeploymentTemplatesData = DeploymentTemplate[];

export type GenerateOnboardingConfigsData = any;

export type GenerateOnboardingConfigsError = HTTPValidationError;

export type GetPendingUsersData = PendingUserListResponse;

export type ApproveRejectUserData = ApproveRejectResponse;

export type ApproveRejectUserError = HTTPValidationError;

export type GetAvailableDomainsData = DomainListResponse;

export type AssignUserDomainData = AssignDomainResponse;

export type AssignUserDomainError = HTTPValidationError;

export interface GetAllUsersParams {
  /**
   * Approval Status List Str
   * Comma-separated list of approval statuses to filter by (e.g., 'approved' or 'rejected')
   */
  approval_status_list_str?: string | null;
}

export type GetAllUsersData = UserListResponse;

export type GetAllUsersError = HTTPValidationError;

export type CreateExpertTipEntryData = any;

export type CreateExpertTipEntryError = HTTPValidationError;

export type CreateCustomerData = CustomerResponse;

export type CreateCustomerError = HTTPValidationError;

export interface ListCustomersParams {
  /** Status */
  status?: string | null;
  /** License Tier */
  license_tier?: string | null;
  /**
   * Limit
   * @default 100
   */
  limit?: number;
}

/** Response List Customers */
export type ListCustomersData = CustomerResponse[];

export type ListCustomersError = HTTPValidationError;

export interface GetCustomerParams {
  /** Customer Id */
  customerId: string;
}

export type GetCustomerData = CustomerResponse;

export type GetCustomerError = HTTPValidationError;

export interface UpdateCustomerParams {
  /** Customer Id */
  customerId: string;
}

export type UpdateCustomerData = CustomerResponse;

export type UpdateCustomerError = HTTPValidationError;

export interface DeleteCustomerParams {
  /**
   * Confirm
   * @default false
   */
  confirm?: boolean;
  /** Customer Id */
  customerId: string;
}

/** Response Delete Customer */
export type DeleteCustomerData = Record<string, any>;

export type DeleteCustomerError = HTTPValidationError;

export interface UpgradeLicenseParams {
  /** Customer Id */
  customerId: string;
}

export type UpgradeLicenseData = CustomerResponse;

export type UpgradeLicenseError = HTTPValidationError;

export interface SuspendCustomerParams {
  /** Customer Id */
  customerId: string;
}

/** Response Suspend Customer */
export type SuspendCustomerData = Record<string, any>;

export type SuspendCustomerError = HTTPValidationError;

export interface ActivateCustomerParams {
  /** Customer Id */
  customerId: string;
}

/** Response Activate Customer */
export type ActivateCustomerData = Record<string, any>;

export type ActivateCustomerError = HTTPValidationError;

export interface CheckQuotaParams {
  /** Customer Id */
  customerId: string;
}

export type CheckQuotaData = QuotaResponse;

export type CheckQuotaError = HTTPValidationError;

export type BootstrapControlPlaneEndpointData = BootstrapResponse;

export type BootstrapControlPlaneEndpointError = HTTPValidationError;

export type JoinWorkerNodeData = JoinNodeResponse;

export type JoinWorkerNodeError = HTTPValidationError;

/** Response List Cluster Nodes */
export type ListClusterNodesData = NodeInfo[];

export type GetClusterStatusData = ClusterStatus;

export interface GetNodeDetailsParams {
  /** Node Name */
  nodeName: string;
}

export type GetNodeDetailsData = NodeInfo;

export type GetNodeDetailsError = HTTPValidationError;

export type HandleZtpCompletionData = ZTPCompletionResponse;

export type HandleZtpCompletionError = HTTPValidationError;

export type UploadTechnicianFileV2Data = FileUploadResponse;

export type UploadTechnicianFileV2Error = HTTPValidationError;

export type GenerateLlmDraftReportData = ReportGenerationResponse;

export type GenerateLlmDraftReportError = HTTPValidationError;

export type SaveFinalizedReportData = ReportSaveResponse;

export type SaveFinalizedReportError = HTTPValidationError;

/** Response Get My Reports */
export type GetMyReportsData = ReportGetResponse[];

export interface GetSpecificReportParams {
  /** Report Id */
  reportId: string;
}

export type GetSpecificReportData = ReportGetResponse;

export type GetSpecificReportError = HTTPValidationError;

export type DirectApproveUser2Data = DirectRegistrationResponse;

export type DirectApproveUser2Error = HTTPValidationError;

export type DirectApproveUserData = any;

export type DirectApproveUserError = HTTPValidationError;

export type UploadDocumentData = any;

export type UploadDocumentError = HTTPValidationError;

export interface GetDocumentStatusParams {
  /** Doc Id */
  docId: string;
}

export type GetDocumentStatusData = DocumentStatus;

export type GetDocumentStatusError = HTTPValidationError;

export interface ListDocumentsParams {
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
}

export type ListDocumentsData = DocumentListResponse;

export type ListDocumentsError = HTTPValidationError;

export type GetDocumentMetricsSummaryData = DocumentMetricsSummary;

export interface GetDocumentOptimalParams {
  /** Doc Id */
  docId: string;
}

export type GetDocumentOptimalData = DocumentResponse;

export type GetDocumentOptimalError = HTTPValidationError;

export interface GetDocumentParams {
  /** Doc Id */
  docId: string;
}

export type GetDocumentData = DocumentResponse;

export type GetDocumentError = HTTPValidationError;

export interface DeleteDocumentParams {
  /** Doc Id */
  docId: string;
}

export type DeleteDocumentData = any;

export type DeleteDocumentError = HTTPValidationError;

export interface GetSecureDocumentUrlParams {
  /** Document Id */
  documentId: string;
}

export type GetSecureDocumentUrlData = SecureUrlResponse;

export type GetSecureDocumentUrlError = HTTPValidationError;

export interface UpdateDocumentParams {
  /** Document Id */
  documentId: string;
}

export type UpdateDocumentData = any;

export type UpdateDocumentError = HTTPValidationError;

export interface GetAdminMetricsParams {
  /**
   * Company
   * Filter metrics by company
   */
  company?: string | null;
}

export type GetAdminMetricsData = any;

export type GetAdminMetricsError = HTTPValidationError;

export type ReprocessStuckDocumentData = ReprocessResponse;

export type ReprocessStuckDocumentError = HTTPValidationError;
