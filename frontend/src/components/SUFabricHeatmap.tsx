/**
 * SU Fabric Heatmap Component
 * 
 * The "8-Rail Grid of Truth" - visualizes Racks × Planes for a Scalable Unit.
 * 
 * **Grid Structure:**
 * - Rows: Racks 1-8 (vertical axis)
 * - Columns: Planes 0-7 (horizontal axis, representing InfiniBand rails)
 * - Cells: Leaf switches at each (Rack, Plane) intersection
 * 
 * **Why This Matters:**
 * In NVIDIA GPU clusters, each rack has 8 leaf switches (one per plane/rail).
 * This grid lets you see at a glance:
 * - Which racks are fully provisioned (all 8 planes green)
 * - Which planes have issues (e.g., Plane 3 has red cells across multiple racks)
 * - Bottlenecks in provisioning flow (e.g., all switches stuck in "Configuring")
 * 
 * **Color Mapping:**
 * PLANNED → Grey (in inventory, not yet on network)
 * DISCOVERY → Blue (Stage 1: reporting serial number)
 * CONFIGURING → Yellow (Stage 2: ZTP pushing 8-rail IP matrix)
 * VALIDATING → Purple (LLDP check comparing wiring to GPU mapper)
 * OPERATIONAL → Green (Full match, BGP up, ready for compute)
 * ERROR → Red (Identity mismatch or wiring violation)
 */

import React from 'react';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';

export interface Props {
  suNumber: number; // Scalable Unit number (1-4)
  switches: SwitchStatus[]; // All switches from Firestore
  onSwitchSelect: (switchData: SelectedSwitch) => void; // Callback when cell clicked
  selectedSwitch: SelectedSwitch | null; // Currently selected switch
}

export interface SwitchStatus {
  switchId: string;
  deviceName: string;
  planeId: number;
  leafId: number;
  rackId: number;
  status: string; // PLANNED, DISCOVERY, CONFIGURING, VALIDATING, OPERATIONAL, ERROR
  cablingHealthPercentage?: number;
  macAddress?: string;
  ipAddress?: string;
  hasSuContamination?: boolean;  // NEW: Cross-SU boundary breach flag
  hasRailContamination?: boolean;  // Rail isolation breach flag
}

export interface SelectedSwitch {
  switchId: string;
  planeId: number;
  leafId: number;
  rackId: number;
  status: string;
}

// Map status to color classes
const getStatusColor = (status: string): string => {
  switch (status) {
    case 'PLANNED':
      return 'bg-gray-300 dark:bg-gray-600 text-gray-700 dark:text-gray-300';
    case 'DISCOVERY':
    case 'DISCOVERY_VERIFIED':
      return 'bg-blue-500 text-white';
    case 'CONFIGURING':
    case 'PROVISIONING':
    case 'ZTP_IN_PROGRESS':
      return 'bg-yellow-500 text-white';
    case 'VALIDATING':
    case 'VALIDATING_CABLING':
      return 'bg-purple-500 text-white';
    case 'OPERATIONAL':
      return 'bg-green-500 text-white';
    case 'ERROR':
    case 'WIRING_ERROR':
    case 'IDENTITY_MISMATCH':
    case 'BLOCKED_IDENTITY_MISMATCH':
      return 'bg-red-500 text-white';
    default:
      return 'bg-gray-200 dark:bg-gray-700 text-gray-500';
  }
};

// Get status display name
const getStatusLabel = (status: string): string => {
  switch (status) {
    case 'PLANNED': return 'Planned';
    case 'DISCOVERY':
    case 'DISCOVERY_VERIFIED': return 'Discovery';
    case 'CONFIGURING':
    case 'PROVISIONING':
    case 'ZTP_IN_PROGRESS': return 'Configuring';
    case 'VALIDATING':
    case 'VALIDATING_CABLING': return 'Validating';
    case 'OPERATIONAL': return 'Operational';
    case 'ERROR':
    case 'WIRING_ERROR':
    case 'IDENTITY_MISMATCH':
    case 'BLOCKED_IDENTITY_MISMATCH': return 'Error';
    default: return 'Unknown';
  }
};

export function SUFabricHeatmap({ suNumber, switches, onSwitchSelect, selectedSwitch }: Props) {
  const racks = [1, 2, 3, 4, 5, 6, 7, 8]; // 8 racks per SU
  const planes = [0, 1, 2, 3, 4, 5, 6, 7]; // 8 planes (InfiniBand rails)

  // Find switch for a given rack and plane
  const getSwitchForCell = (rackId: number, planeId: number): SwitchStatus | null => {
    return switches.find(
      (s) => s.rackId === rackId && s.planeId === planeId
    ) || null;
  };

  // Check if cell is selected
  const isCellSelected = (rackId: number, planeId: number): boolean => {
    if (!selectedSwitch) return false;
    return selectedSwitch.rackId === rackId && selectedSwitch.planeId === planeId;
  };

  return (
    <div className="space-y-4">
      <div className="text-sm text-muted-foreground mb-2">
        <strong>SU-{suNumber}</strong> — 8 Racks × 8 Planes (64 Leaf Switches)
      </div>

      {/* Grid Container */}
      <div className="inline-block border border-border rounded-lg overflow-hidden">
        {/* Header Row: Plane IDs */}
        <div className="grid grid-cols-9 bg-muted">
          <div className="p-2 text-center text-xs font-semibold border-r border-border">
            Rack \ Plane
          </div>
          {planes.map((planeId) => (
            <div
              key={planeId}
              className="p-2 text-center text-xs font-semibold border-r border-border last:border-r-0"
            >
              P{planeId}
            </div>
          ))}
        </div>

        {/* Grid Rows: Each rack */}
        {racks.map((rackId) => (
          <div key={rackId} className="grid grid-cols-9 border-t border-border">
            {/* Rack Label */}
            <div className="p-2 text-center text-xs font-semibold bg-muted border-r border-border flex items-center justify-center">
              R{rackId}
            </div>

            {/* Cells: One per plane */}
            {planes.map((planeId) => {
              const switchData = getSwitchForCell(rackId, planeId);
              const isSelected = isCellSelected(rackId, planeId);

              if (!switchData) {
                // Empty cell (no switch defined for this rack/plane)
                return (
                  <div
                    key={planeId}
                    className="w-16 h-16 border-r border-border last:border-r-0 bg-gray-50 dark:bg-gray-900 flex items-center justify-center"
                  >
                    <span className="text-xs text-muted-foreground">—</span>
                  </div>
                );
              }

              const statusColor = getStatusColor(switchData.status);
              const statusLabel = getStatusLabel(switchData.status);
              
              // CRITICAL: Determine if cell should pulse red for violations
              const hasCriticalViolation = switchData.hasSuContamination || switchData.hasRailContamination;
              const shouldPulseRed = switchData.hasSuContamination;  // SU breaches get pulse-red priority

              return (
                <TooltipProvider key={planeId}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        onClick={() => onSwitchSelect({
                          switchId: switchData.switchId,
                          planeId: switchData.planeId,
                          leafId: switchData.leafId,
                          rackId: switchData.rackId,
                          status: switchData.status
                        })}
                        className={cn(
                          'w-16 h-16 border-r border-border last:border-r-0 transition-all',
                          'flex flex-col items-center justify-center gap-1',
                          'hover:opacity-80 hover:scale-105 cursor-pointer',
                          'relative',
                          hasCriticalViolation ? 'bg-red-600 text-white' : statusColor,
                          shouldPulseRed && 'animate-pulse',  // Pulse animation for SU breaches
                          isSelected && 'ring-4 ring-orange-500 ring-offset-2 scale-110 z-10'
                        )}
                      >
                        {/* SU Contamination Indicator (HIGHEST PRIORITY) */}
                        {switchData.hasSuContamination && (
                          <div className="absolute -top-1 -right-1 text-xl animate-pulse">
                            🔴
                          </div>
                        )}
                        
                        {/* Rail Contamination Indicator (if no SU breach) */}
                        {!switchData.hasSuContamination && switchData.hasRailContamination && (
                          <div className="absolute -top-1 -right-1 text-xl">
                            🚨
                          </div>
                        )}
                        
                        <div className="text-[10px] font-mono font-semibold">
                          L{switchData.leafId}
                        </div>
                        {switchData.cablingHealthPercentage !== undefined && (
                          <div className="text-[8px] font-mono opacity-90">
                            {switchData.cablingHealthPercentage.toFixed(0)}%
                          </div>
                        )}
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-xs">
                      <div className="space-y-1">
                        <div className="font-semibold">{switchData.deviceName}</div>
                        <div className="text-xs space-y-0.5">
                          <div>Rack {rackId}, Plane {planeId}, Leaf {switchData.leafId}</div>
                          <div>
                            <Badge variant="outline" className="text-[10px]">
                              {statusLabel}
                            </Badge>
                          </div>
                          {switchData.ipAddress && (
                            <div className="font-mono">{switchData.ipAddress}</div>
                          )}
                          {switchData.cablingHealthPercentage !== undefined && (
                            <div>Cabling: {switchData.cablingHealthPercentage.toFixed(1)}%</div>
                          )}
                        </div>
                      </div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              );
            })}
          </div>
        ))}
      </div>

      {/* Summary Stats */}
      <div className="text-xs text-muted-foreground">
        Click any cell to view port-level cabling details and validation results.
      </div>
    </div>
  );
}
