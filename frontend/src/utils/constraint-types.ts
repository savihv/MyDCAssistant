/**
 * Type definitions for multi-domain constraint system
 * Phase 1: Foundation for domain-specific compliance constraints
 */

/**
 * Domain Types
 * Represents different industry verticals and use cases
 */
export type DomainType = 
  | 'dcdc'           // Data Center Deployment & Commissioning
  | 'healthcare'     // Healthcare/HIPAA compliance
  | 'manufacturing'  // Manufacturing/OSHA compliance
  | 'finance'        // Financial Services/SOX compliance
  | 'custom';        // User-defined custom domain

/**
 * Category Types
 * Classifies constraints by functional area
 */
export type CategoryType = 
  | 'safety'         // Physical safety rules and requirements
  | 'compliance'     // Regulatory compliance requirements
  | 'workflow'       // Process and sequence requirements
  | 'equipment'      // Equipment-specific rules
  | 'policy';        // Company policy and best practices

/**
 * Severity Types
 * Defines the criticality level of each constraint
 */
export type SeverityType = 
  | 'critical'       // Must NEVER violate - blocks non-compliant actions
  | 'warning'        // Should strongly avoid - warns but doesn't block
  | 'info';          // Best practice - informational guidance

/**
 * Constraint Context
 * Optional filters that define when/where a constraint applies
 */
export interface ConstraintContext {
  /** Phases where this constraint applies (e.g., "Installation", "Testing") */
  appliesToPhase?: string[];
  
  /** Equipment types this constraint applies to (e.g., "Dell PowerEdge R750") */
  appliesToEquipment?: string[];
  
  /** Roles this constraint applies to (e.g., "Technician", "Lead Tech") */
  appliesToRole?: string[];
}

/**
 * Constraint Document
 * Complete constraint schema matching Firestore structure
 * 
 * Firestore Path: artifacts/{appId}/users/{userId}/constraints/{constraintId}
 */
export interface Constraint {
  // ========== Identity ==========
  /** Firestore document ID (auto-generated or custom) */
  id: string;
  
  // ========== Classification ==========
  /** Domain this constraint belongs to */
  domain: DomainType;
  
  /** Functional category */
  category: CategoryType;
  
  /** Criticality level */
  severity: SeverityType;
  
  // ========== Content ==========
  /** The constraint rule text (max 500 characters) */
  rule: string;
  
  /** Explanation of why this rule exists (max 1000 characters) */
  reasoning: string;
  
  // ========== Context (Optional) ==========
  /** Optional filters for when/where this constraint applies */
  context?: ConstraintContext;
  
  // ========== Metadata (Optional) ==========
  /** Source reference (e.g., "OSHA 1910.147", "Internal SOP v2.3") */
  source?: string;
  
  /** Priority for conflict resolution (1-10, default: 5) */
  priority?: number;
  
  // ========== Lifecycle ==========
  /** Whether this constraint is currently active (allows disable without delete) */
  active: boolean;
  
  /** User ID who created this constraint */
  createdBy: string;
  
  /** Timestamp when constraint was created */
  createdAt: any; // Firestore Timestamp type
  
  /** Timestamp when constraint was last updated */
  updatedAt: any; // Firestore Timestamp type
  
  // ========== Phase 2 (Reserved) ==========
  /** Firebase Storage URL for visual constraint (added in Phase 2) */
  imageUrl?: string;
}

/**
 * User Profile Extension
 * Additional fields added to user profile for domain configuration
 */
export interface UserProfileDomainConfig {
  /** Selected domain for this user */
  domain: DomainType;
  
  /** Custom domain name (only if domain === 'custom') */
  customDomainName?: string;
  
  /** Current work phase for advanced filtering */
  currentPhase?: string;
  
  /** Current role context for advanced filtering */
  currentRole?: string;
}

/**
 * Constraint Summary Statistics
 * Used for analytics and UI display
 */
export interface ConstraintSummary {
  /** Total number of constraints */
  total: number;
  
  /** Count by severity level */
  bySeverity: {
    critical: number;
    warning: number;
    info: number;
  };
  
  /** Count by category */
  byCategory: {
    safety: number;
    compliance: number;
    workflow: number;
    equipment: number;
    policy: number;
  };
}

/**
 * Helper type for constraint creation (omits auto-generated fields)
 */
export type ConstraintCreate = Omit<Constraint, 'id' | 'createdAt' | 'updatedAt'>;

/**
 * Helper type for constraint updates (allows partial updates)
 */
export type ConstraintUpdate = Partial<Omit<Constraint, 'id' | 'createdBy' | 'createdAt'>>;
