/**
 * Cabling Detail Pane Component
 * 
 * The "Fix-It" panel that slides out when an Installation Lead clicks a red/yellow cell.
 * 
 * **Purpose:**
 * Shows port-level validation results from POST /api/ztp/validate-cabling.
 * Displays exactly which cables are mis-wired and provides actionable swap recommendations.
 * 
 * **What the Lead Sees:**
 * - Alert header: "Rack 04, Leaf 2 (Plane 0) - 87.5% Healthy"
 * - Port-by-port status table:
 *   - Port 17: ❌ FAILURE
 *     - Expected: GPU-1, Srv-09, Tail-0
 *     - Actual: GPU-1, Srv-10, Tail-0
 *     - Action: Swap cables between Port 17 and Port 19
 * - Manual override controls:
 *   - "Accept Serial Number" (for last-minute hardware changes)
 *   - "Mark As Resolved" (after physical fix)
 * 
 * **Integration:**
 * Fetches validation results from Firestore provisioning_alerts collection.
 * Calls POST /api/ztp/validate-cabling to re-run validation after fixes.
 */

import React, { useEffect, useState } from 'react';
import { X, AlertTriangle, CheckCircle2, MinusCircle, RefreshCw, WifiOff } from 'lucide-react';
import { Button } from "../components/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../extensions/shadcn/components/card";
import { Badge } from "../extensions/shadcn/components/badge";
import { Alert, AlertDescription } from "../extensions/shadcn/components/alert";
import { Separator } from "../extensions/shadcn/components/separator";
import { ScrollArea } from "../extensions/shadcn/components/scroll-area";
import { apiClient } from "../app";
import type { 
  CablingValidationRequest,
  CablingValidationResponse, 
  PortValidationResultModel,
  LLDPNeighbor 
} from "../apiclient/data-contracts";
import { firebaseApp } from "../app";
import { getFirestore } from 'firebase/firestore';
import { doc, getDoc, collection, query, where, getDocs } from 'firebase/firestore';


export interface Props {
  switchData: {
    switchId: string;
    planeId: number;
    leafId: number;
    rackId: number;
    status: string;
  };
  onClose: () => void;
}

interface ValidationResult {
  port_id: string;
  port_number: number;
  status: string;
  expected_neighbor: string;
  actual_neighbor: string | null;
  mismatch_details: string | null;
  swap_recommendation: string | null;
}

interface ValidationSummary {
  status: string;
  switch_id: string;
  plane_id: number;
  leaf_id: number;
  cluster_healthy: boolean;
  total_ports: number;
  passed: number;
  failed: number;
  missing: number;
  health_percentage: number;
  results: ValidationResult[];
  swap_recommendations: string[];
  rail_violations: any[];
  has_rail_contamination: boolean;
  su_violations: any[];  // NEW: Cross-SU boundary violations
  has_su_contamination: boolean;  // NEW: Priority triage flag
}

export function CablingDetailPane({ switchData, onClose }: Props) {
  const [isValidating, setIsValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<CablingValidationResponse | null>(null);
  const [lldpNeighbors, setLldpNeighbors] = useState<LLDPNeighbor[]>([]);
  const [isLoadingLLDP, setIsLoadingLLDP] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const firestore = getFirestore(firebaseApp);

  const [validationResults, setValidationResults] = useState<ValidationSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    loadValidationResults();
  }, [switchData.switchId]);

  const loadValidationResults = async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Step 1: Fetch LLDP neighbors from Firestore
      const switchDocRef = doc(firestore, 'live_infrastructure', switchData.switchId);
      const switchDoc = await getDoc(switchDocRef);
      
      if (!switchDoc.exists()) {
        throw new Error('Switch not found in Firestore');
      }

      const switchDocData = switchDoc.data();
      const lldpNeighbors: LLDPNeighbor[] = switchDocData.lldp_neighbors || [];

      // Step 2: Call POST /validate-cabling endpoint
      const requestBody: CablingValidationRequest = {
        switch_id: switchData.switchId,
        plane_id: switchData.planeId,
        leaf_id: switchData.leafId,
        neighbors: lldpNeighbors
      };

      const response = await apiClient.validate_cabling(requestBody);
      const data: CablingValidationResponse = await response.json();

      // Transform to UI format
      const summary: ValidationSummary = {
        status: data.status,
        switch_id: data.switch_id,
        plane_id: data.plane_id,
        leaf_id: data.leaf_id,
        cluster_healthy: data.cluster_healthy,
        total_ports: data.total_ports,
        passed: data.passed,
        failed: data.failed,
        missing: data.missing,
        health_percentage: data.health_percentage,
        results: data.results.map(r => ({
          port_id: r.port_id,
          port_number: r.port_number,
          status: r.status,
          expected_neighbor: r.expected_neighbor,
          actual_neighbor: r.actual_neighbor || null,
          mismatch_details: r.mismatch_details || null,
          swap_recommendation: r.swap_recommendation || null
        })),
        swap_recommendations: data.swap_recommendations || [],
        rail_violations: data.rail_violations || [],
        has_rail_contamination: data.has_rail_contamination || false,
        su_violations: data.su_violations || [],  // NEW: Cross-SU boundary violations
        has_su_contamination: data.has_su_contamination || false  // NEW: Priority triage flag
      };

      setValidationResults(summary);
    } catch (err: any) {
      console.error('Validation error:', err);
      setError(err.message || 'Failed to load validation results');
    } finally {
      setIsLoading(false);
    }
  };

  // Re-run validation (after technician fixes cables)
  const handleRevalidate = async () => {
    await loadValidationResults();
  };

  // Manual override: Accept current serial number
  const handleAcceptSerial = async () => {
    if (!confirm('Accept detected hardware and update inventory?')) return;
    // TODO: Call update inventory endpoint
    console.log('Accepting serial for', switchData.switchId);
  };

  // Get icon for validation status
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'PASS':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'FAIL':
        return <AlertTriangle className="h-4 w-4 text-red-500" />;
      case 'MISSING':
        return <WifiOff className="h-4 w-4 text-orange-500" />;
      default:
        return <MinusCircle className="h-4 w-4 text-gray-400" />;
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 w-full md:w-2/3 lg:w-1/2 bg-background border-l border-border shadow-2xl z-50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-6 border-b border-border">
        <div>
          <h2 className="text-2xl font-bold">{switchData.switchId}</h2>
          <p className="text-sm text-muted-foreground">
            Rack {switchData.rackId} • Plane {switchData.planeId} • Leaf {switchData.leafId}
          </p>
        </div>
        <Button onClick={onClose} variant="ghost" size="sm">
          <X className="h-5 w-5" />
        </Button>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1 p-6">
        {isLoading && (
          <div className="text-center py-12">
            <RefreshCw className="h-8 w-8 animate-spin mx-auto text-blue-500" />
            <p className="text-sm text-muted-foreground mt-2">Loading validation results...</p>
          </div>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {validationResults && (
          <div className="space-y-6">
            {/* Health Summary */}
            <Card>
              <CardHeader>
                <CardTitle>Cabling Health</CardTitle>
                <CardDescription>
                  {validationResults.cluster_healthy ? (
                    <span className="text-green-600 font-semibold">✓ All ports validated successfully</span>
                  ) : (
                    <span className="text-red-600 font-semibold">⚠ Mis-wires detected</span>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-4 gap-4 text-center">
                  <div>
                    <div className="text-2xl font-bold">{validationResults.health_percentage.toFixed(1)}%</div>
                    <div className="text-xs text-muted-foreground">Health</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-green-600">{validationResults.passed}</div>
                    <div className="text-xs text-muted-foreground">Passed</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-red-600">{validationResults.failed}</div>
                    <div className="text-xs text-muted-foreground">Failed</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-orange-600">{validationResults.missing}</div>
                    <div className="text-xs text-muted-foreground">Missing</div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* SU Boundary Contamination Alert (HIGHEST PRIORITY) */}
            {validationResults.has_su_contamination && validationResults.su_violations && validationResults.su_violations.length > 0 && (
              <Alert variant="destructive" className="border-red-700 bg-red-100 dark:bg-red-950 animate-pulse">
                <div className="flex items-start gap-3">
                  <span className="text-3xl">🔴</span>
                  <div className="flex-1">
                    <div className="font-bold text-xl text-red-900 dark:text-red-100 mb-2">
                      ⚠️ CRITICAL: Cross-SU Boundary Violation Detected
                    </div>
                    <p className="text-sm text-red-900 dark:text-red-200 mb-4">
                      This switch is cabled to devices from a DIFFERENT Scalable Unit. This indicates systemic deployment error—wrong rack placement or switch role confusion.
                      <strong className="block mt-2 text-base">🚫 HIGHEST PRIORITY: STOP DEPLOYMENT UNTIL RESOLVED</strong>
                    </p>
                    
                    {/* SU Violation Table */}
                    <div className="bg-white dark:bg-gray-900 rounded-lg border-2 border-red-400 dark:border-red-600 overflow-hidden">
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-red-200 dark:bg-red-900/70">
                            <tr>
                              <th className="px-4 py-2 text-left font-bold text-red-900 dark:text-red-100">Port</th>
                              <th className="px-4 py-2 text-left font-bold text-red-900 dark:text-red-100">Neighbor Hostname</th>
                              <th className="px-4 py-2 text-left font-bold text-red-900 dark:text-red-100">Expected SU</th>
                              <th className="px-4 py-2 text-left font-bold text-red-900 dark:text-red-100">Actual SU</th>
                              <th className="px-4 py-2 text-left font-bold text-red-900 dark:text-red-100">Remediation</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-red-300 dark:divide-red-700">
                            {validationResults.su_violations.map((violation, idx) => (
                              <tr key={idx} className="hover:bg-red-100 dark:hover:bg-red-900/30">
                                <td className="px-4 py-3 font-mono font-bold text-red-900 dark:text-red-100">
                                  {violation.port_id}
                                </td>
                                <td className="px-4 py-3 font-mono text-xs text-red-800 dark:text-red-200">
                                  {violation.neighbor_hostname}
                                </td>
                                <td className="px-4 py-3">
                                  <Badge variant="outline" className="border-green-600 text-green-700 dark:text-green-400 font-bold">
                                    SU-{violation.expected_su_id} ✅
                                  </Badge>
                                </td>
                                <td className="px-4 py-3">
                                  <Badge variant="outline" className="font-bold">
                                    SU-{violation.actual_su_id} ❌
                                  </Badge>
                                </td>
                                <td className="px-4 py-3 text-xs">
                                  <div className="bg-yellow-100 dark:bg-yellow-900/30 text-yellow-900 dark:text-yellow-200 px-2 py-1 rounded font-bold border border-yellow-400">
                                    {violation.action}
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {/* Impact Summary */}
                    <div className="mt-4 p-4 bg-red-200 dark:bg-red-900/50 rounded border-2 border-red-400 dark:border-red-600">
                      <p className="text-sm font-bold text-red-900 dark:text-red-100 mb-2">
                        🎯 Critical Impact:
                      </p>
                      <ul className="text-sm text-red-900 dark:text-red-200 space-y-1 ml-4 list-disc">
                        <li><strong>Performance Degradation:</strong> 15-40% All-Reduce throughput loss</li>
                        <li><strong>Wrong IP Schema:</strong> GPU endpoints using incorrect SU global offsets</li>
                        <li><strong>BGP Routing Chaos:</strong> Cross-SU traffic violating ASN isolation</li>
                        <li><strong>Fabric Instability:</strong> Non-deterministic packet routing across SuperPOD</li>
                        <li className="font-bold text-base mt-2">⚠️ This is NOT a simple cable swap—verify physical switch location immediately</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </Alert>
            )}

            {/* Rail Contamination Alert (CRITICAL) */}
            {validationResults.has_rail_contamination && validationResults.rail_violations && validationResults.rail_violations.length > 0 && (
              <Alert variant="destructive" className="border-red-600 bg-red-50 dark:bg-red-950">
                <div className="flex items-start gap-3">
                  <span className="text-2xl">🚨</span>
                  <div className="flex-1">
                    <div className="font-bold text-lg text-red-900 dark:text-red-100 mb-2">
                      CRITICAL: Rail Contamination Detected
                    </div>
                    <p className="text-sm text-red-800 dark:text-red-200 mb-4">
                      Cross-plane wiring detected. This will degrade All-Reduce operations by 15-40% and break GPUDirect RDMA.
                      <strong className="block mt-1">⚠️ BLOCK COMPUTE RELEASE UNTIL RESOLVED</strong>
                    </p>
                    
                    {/* Rail Violation Table */}
                    <div className="bg-white dark:bg-gray-900 rounded-lg border border-red-300 dark:border-red-700 overflow-hidden">
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-red-100 dark:bg-red-900/50">
                            <tr>
                              <th className="px-4 py-2 text-left font-semibold text-red-900 dark:text-red-100">Port</th>
                              <th className="px-4 py-2 text-left font-semibold text-red-900 dark:text-red-100">Expected Plane</th>
                              <th className="px-4 py-2 text-left font-semibold text-red-900 dark:text-red-100">Detected Tail</th>
                              <th className="px-4 py-2 text-left font-semibold text-red-900 dark:text-red-100">Neighbor Hostname</th>
                              <th className="px-4 py-2 text-left font-semibold text-red-900 dark:text-red-100">Action</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-red-200 dark:divide-red-800">
                            {validationResults.rail_violations.map((violation, idx) => (
                              <tr key={idx} className="hover:bg-red-50 dark:hover:bg-red-900/20">
                                <td className="px-4 py-3 font-mono font-semibold text-red-900 dark:text-red-100">
                                  {violation.port_id}
                                </td>
                                <td className="px-4 py-3">
                                  <Badge variant="outline" className="border-green-600 text-green-700 dark:text-green-400">
                                    Plane {violation.expected_plane} (Tail-{violation.expected_plane})
                                  </Badge>
                                </td>
                                <td className="px-4 py-3">
                                  {violation.actual_tail !== null ? (
                                    <Badge variant="outline">
                                      Tail-{violation.actual_tail} ❌
                                    </Badge>
                                  ) : (
                                    <Badge variant="outline">
                                      Unknown ❓
                                    </Badge>
                                  )}
                                </td>
                                <td className="px-4 py-3 font-mono text-xs text-red-800 dark:text-red-200">
                                  {violation.neighbor_hostname}
                                </td>
                                <td className="px-4 py-3 text-xs">
                                  <div className="bg-blue-100 dark:bg-blue-900/30 text-blue-900 dark:text-blue-200 px-2 py-1 rounded font-semibold">
                                    {violation.action}
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {/* Impact Summary */}
                    <div className="mt-4 p-3 bg-red-100 dark:bg-red-900/30 rounded border border-red-300 dark:border-red-700">
                      <p className="text-xs font-semibold text-red-900 dark:text-red-100 mb-1">
                        📊 Impact Analysis:
                      </p>
                      <ul className="text-xs text-red-800 dark:text-red-200 space-y-1 ml-4 list-disc">
                        <li>All-Reduce throughput degraded by 15-40%</li>
                        <li>Non-deterministic routing across InfiniBand rails</li>
                        <li>GPUDirect RDMA failures during training</li>
                        <li>Performance issues discovered during $50K+ production runs</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </Alert>
            )}

            {/* Swap Recommendations */}
            {validationResults.swap_recommendations.length > 0 && (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  <strong>Quick Fix Recommendations:</strong>
                  <ul className="list-disc list-inside mt-2 space-y-1">
                    {validationResults.swap_recommendations.map((rec, idx) => (
                      <li key={idx} className="text-sm">{rec}</li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            )}

            {/* Port-Level Results */}
            <Card>
              <CardHeader>
                <CardTitle>Port-Level Validation</CardTitle>
                <CardDescription>
                  Showing only ports with issues. {validationResults.passed} ports passed validation.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {validationResults.results
                    .filter((r) => r.status !== 'PASS')
                    .map((result) => (
                      <div key={result.port_id} className="border border-border rounded-lg p-4">
                        <div className="flex items-start gap-3">
                          {getStatusIcon(result.status)}
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              <span className="font-semibold">Port {result.port_number}</span>
                              <Badge variant={result.status === 'FAIL' ? 'destructive' : 'secondary'}>
                                {result.status}
                              </Badge>
                            </div>

                            <div className="text-sm space-y-2">
                              <div>
                                <span className="text-muted-foreground">Expected:</span>
                                <div className="font-mono text-xs mt-1">{result.expected_neighbor}</div>
                              </div>

                              {result.actual_neighbor && (
                                <div>
                                  <span className="text-muted-foreground">Actual:</span>
                                  <div className="font-mono text-xs mt-1">{result.actual_neighbor}</div>
                                </div>
                              )}

                              {result.mismatch_details && (
                                <div className="text-xs text-muted-foreground italic">
                                  {result.mismatch_details}
                                </div>
                              )}

                              {result.swap_recommendation && (
                                <div className="bg-blue-50 dark:bg-blue-950 p-2 rounded text-xs font-semibold text-blue-700 dark:text-blue-300">
                                  {result.swap_recommendation}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </ScrollArea>

      {/* Footer Actions */}
      <div className="p-6 border-t border-border space-y-3">
        <Button onClick={handleRevalidate} className="w-full" variant="outline">
          <RefreshCw className="h-4 w-4 mr-2" />
          Re-Run Validation
        </Button>
        <div className="grid grid-cols-2 gap-3">
          <Button onClick={handleAcceptSerial} variant="outline">
            Accept Serial
          </Button>
          <Button variant="default">
            Mark Resolved
          </Button>
        </div>
      </div>
    </div>
  );
}
