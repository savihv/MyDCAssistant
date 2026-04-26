import React from "react";
import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { apiClient } from 'app';
import {
  ExtractionResultsResponse,
  Device,
  Connection,
} from 'types';
import {
  Download,
  CheckCircle2,
  AlertTriangle,
  Network,
  Server,
  HardDrive,
  Cable,
  FileText,
  Clock,
  XCircle,
  Zap,
  Shield,
  AlertOctagon,
  Info,
} from 'lucide-react';
import { toast } from 'sonner';

export interface Props {
  projectId: string;
}

export function ResultsView({ projectId }: Props) {
  const [results, setResults] = useState<ExtractionResultsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isExporting, setIsExporting] = useState(false);

  useEffect(() => {
    loadResults();
  }, [projectId]);

  const loadResults = async () => {
    try {
      const response = await apiClient.get_extraction_results({ projectId: projectId });
      const resAny = response as any;
      const data: ExtractionResultsResponse = resAny.data ? resAny.data : (resAny.json ? await resAny.json() : resAny);
      setResults(data);
    } catch (error) {
      toast.error('Failed to load extraction results');
      console.error('Load error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExportMatrix = async () => {
    setIsExporting(true);
    try {
      const response = await fetch(`/api/cluster-bringup/export-cabling-matrix/${projectId}`);
      if (!response.ok) throw new Error('Failed to download CSV matrix');
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `cabling_matrix_${projectId}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success('Cabling matrix exported successfully');
    } catch (error) {
      toast.error('Export failed. Please try again.');
      console.error('Export error:', error);
    } finally {
      setIsExporting(false);
    }
  };

  if (isLoading) {
    return (
      <Card className="p-8 text-center">
        <p className="text-muted-foreground">Loading results...</p>
      </Card>
    );
  }

  if (!results) {
    return (
      <Card className="p-8 text-center">
        <p className="text-muted-foreground">No results available</p>
      </Card>
    );
  }

  const devicesByType = results.devices.reduce((acc, device) => {
    const type = device.deviceType || 'other';
    if (!acc[type]) acc[type] = [];
    acc[type].push(device);
    return acc;
  }, {} as Record<string, Device[]>);

  const connectionsByType = results.connections.reduce((acc, conn) => {
    const type = conn.connectionType || 'unknown';
    if (!acc[type]) acc[type] = [];
    acc[type].push(conn);
    return acc;
  }, {} as Record<string, Connection[]>);

  const validationSummary = (results as any).validation_summary || {};
  
  const devicesByTier = results.devices.reduce((acc, device) => {
    const tier = (device as any)?.network_metadata?.tier || 'UNKNOWN';
    if (!acc[tier]) acc[tier] = [];
    acc[tier].push(device);
    return acc;
  }, {} as Record<string, Device[]>);

  const connectionsBySegment = results.connections.reduce((acc, conn) => {
    const segment = (conn as any).networkSegment || 'UNKNOWN';
    if (!acc[segment]) acc[segment] = [];
    acc[segment].push(conn);
    return acc;
  }, {} as Record<string, Connection[]>);

  const criticalIssuesList = (validationSummary as any).criticalIssues || [];
  const highIssuesList = (validationSummary as any).highIssues || [];
  const mediumIssuesList = (validationSummary as any).mediumIssues || [];
  const warningsList = (validationSummary as any).warnings || [];

  const criticalIssues = criticalIssuesList.length;
  const highIssues = highIssuesList.length;
  const mediumIssues = mediumIssuesList.length;
  const warnings = warningsList.length;
  const totalIssues = criticalIssues + highIssues + mediumIssues;

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/10 rounded">
              <Server className="w-6 h-6 text-blue-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{results.devices.length}</p>
              <p className="text-sm text-muted-foreground">Devices Extracted</p>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-500/10 rounded">
              <Cable className="w-6 h-6 text-green-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{results.connections.length}</p>
              <p className="text-sm text-muted-foreground">Connections Mapped</p>
            </div>
          </div>
        </Card>

        <Card className={`p-6 border-l-4 ${
          criticalIssues > 0 ? 'border-l-red-500' : 
          highIssues > 0 ? 'border-l-orange-500' : 
          mediumIssues > 0 ? 'border-l-yellow-500' : 
          'border-l-green-500'
        }`}>
          <div className="flex items-center gap-3">
            <div
              className={`p-2 rounded ${
                criticalIssues > 0 ? 'bg-red-500/10' : 
                highIssues > 0 ? 'bg-orange-500/10' : 
                mediumIssues > 0 ? 'bg-yellow-500/10' : 
                'bg-green-500/10'
              }`}
            >
              {totalIssues > 0 ? (
                <AlertTriangle className={`w-6 h-6 ${
                  criticalIssues > 0 ? 'text-red-500' : 
                  highIssues > 0 ? 'text-orange-500' : 
                  'text-yellow-500'
                }`} />
              ) : (
                <CheckCircle2 className="w-6 h-6 text-green-500" />
              )}
            </div>
            <div>
              <p className="text-2xl font-bold">
                {totalIssues > 0 ? totalIssues : '✓'}
              </p>
              <p className="text-sm text-muted-foreground">Validation Status</p>
            </div>
          </div>
        </Card>

        <Card className="p-6 border-l-4 border-l-blue-500">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/10 rounded">
              <Shield className="w-6 h-6 text-blue-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{Object.keys(devicesByTier).length}</p>
              <p className="text-sm text-muted-foreground">Network Tiers</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Network Tier Breakdown */}
      <Card className="p-6 bg-gradient-to-br from-blue-500/5 to-purple-500/5">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5" />
          Network Tier Architecture
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Backend Fabric */}
          <Card className="p-4 border-l-4 border-l-blue-600">
            <div className="flex items-center gap-2 mb-3">
              <Zap className="w-5 h-5 text-blue-600" />
              <h4 className="font-semibold text-blue-600">BACKEND_FABRIC</h4>
            </div>
            <p className="text-xs text-muted-foreground mb-3">GPU-to-GPU RDMA Traffic</p>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Devices:</span>
                <Badge variant="outline">{devicesByTier['BACKEND_FABRIC']?.length || 0}</Badge>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Connections:</span>
                <Badge variant="outline">{connectionsBySegment['BACKEND_FABRIC']?.length || 0}</Badge>
              </div>
              <div className="text-xs text-muted-foreground mt-2">
                InfiniBand/RoCE switches, HCA ports
              </div>
            </div>
          </Card>

          {/* Frontend Fabric */}
          <Card className="p-4 border-l-4 border-l-green-600">
            <div className="flex items-center gap-2 mb-3">
              <Network className="w-5 h-5 text-green-600" />
              <h4 className="font-semibold text-green-600">FRONTEND_FABRIC</h4>
            </div>
            <p className="text-xs text-muted-foreground mb-3">Client & Storage Access</p>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Devices:</span>
                <Badge variant="outline">{devicesByTier['FRONTEND_FABRIC']?.length || 0}</Badge>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Connections:</span>
                <Badge variant="outline">{connectionsBySegment['FRONTEND_FABRIC']?.length || 0}</Badge>
              </div>
              <div className="text-xs text-muted-foreground mt-2">
                Ethernet switches, server NICs
              </div>
            </div>
          </Card>

          {/* OOB Management */}
          <Card className="p-4 border-l-4 border-l-orange-600">
            <div className="flex items-center gap-2 mb-3">
              <Shield className="w-5 h-5 text-orange-600" />
              <h4 className="font-semibold text-orange-600">OOB_MANAGEMENT</h4>
            </div>
            <p className="text-xs text-muted-foreground mb-3">Control Plane & BMC</p>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Devices:</span>
                <Badge variant="outline">{devicesByTier['OOB_MANAGEMENT']?.length || 0}</Badge>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Connections:</span>
                <Badge variant="outline">{connectionsBySegment['OOB_MANAGEMENT']?.length || 0}</Badge>
              </div>
              <div className="text-xs text-muted-foreground mt-2">
                Management switches, BMC ports
              </div>
            </div>
          </Card>
        </div>
      </Card>

      {/* Severity-Based Validation Alerts */}
      {criticalIssues > 0 && (
        <Alert variant="destructive" className="border-l-4 border-l-red-600">
          <AlertOctagon className="h-5 w-5" />
          <AlertTitle className="font-bold text-lg">CRITICAL: Deployment Blockers ({criticalIssues})</AlertTitle>
          <AlertDescription className="mt-2">
            <p className="font-semibold mb-2">These issues will prevent cluster operation. Must be fixed before deployment:</p>
            <ul className="space-y-2 ml-4">
              {criticalIssuesList.slice(0, 5).map((issue: any, idx: number) => (
                <li key={idx} className="text-sm">
                  <span className="font-semibold">{issue.type}:</span> {issue.message}
                  <div className="text-xs text-muted-foreground mt-1">
                    <strong>Impact:</strong> {issue.impact}
                  </div>
                  <div className="text-xs text-blue-400 mt-1">
                    <strong>Fix:</strong> {issue.recommendation}
                  </div>
                </li>
              ))}
            </ul>
            {criticalIssuesList.length > 5 && (
              <p className="text-xs mt-2 text-muted-foreground">+ {criticalIssuesList.length - 5} more critical issues</p>
            )}
          </AlertDescription>
        </Alert>
      )}

      {highIssues > 0 && (
        <Alert className="border-l-4 border-l-orange-600 bg-orange-500/5">
          <AlertTriangle className="h-5 w-5 text-orange-600" />
          <AlertTitle className="font-bold text-lg text-orange-600">HIGH: Performance & Security Risks ({highIssues})</AlertTitle>
          <AlertDescription className="mt-2">
            <p className="font-semibold mb-2">These issues will degrade performance or compromise security:</p>
            <ul className="space-y-2 ml-4">
              {highIssuesList.slice(0, 3).map((issue: any, idx: number) => (
                <li key={idx} className="text-sm">
                  <span className="font-semibold">{issue.type}:</span> {issue.message}
                  <div className="text-xs text-muted-foreground mt-1">
                    <strong>Impact:</strong> {issue.impact}
                  </div>
                  <div className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                    <strong>Fix:</strong> {issue.recommendation}
                  </div>
                </li>
              ))}
            </ul>
            {highIssuesList.length > 3 && (
              <p className="text-xs mt-2 text-muted-foreground">+ {highIssuesList.length - 3} more high-priority issues</p>
            )}
          </AlertDescription>
        </Alert>
      )}

      {mediumIssues > 0 && (
        <Alert className="border-l-4 border-l-yellow-600 bg-yellow-500/5">
          <AlertTriangle className="h-5 w-5 text-yellow-600" />
          <AlertTitle className="font-bold text-yellow-600">MEDIUM: Operational Concerns ({mediumIssues})</AlertTitle>
          <AlertDescription className="mt-2">
            <p className="font-semibold mb-2">These issues may cause operational problems:</p>
            <ul className="space-y-2 ml-4">
              {mediumIssuesList.slice(0, 3).map((issue: any, idx: number) => (
                <li key={idx} className="text-sm">
                  <span className="font-semibold">{issue.type}:</span> {issue.message}
                  <div className="text-xs text-muted-foreground mt-1">
                    <strong>Impact:</strong> {issue.impact}
                  </div>
                </li>
              ))}
            </ul>
            {mediumIssuesList.length > 3 && (
              <p className="text-xs mt-2 text-muted-foreground">+ {mediumIssuesList.length - 3} more medium-priority issues</p>
            )}
          </AlertDescription>
        </Alert>
      )}

      {warnings > 0 && (
        <Alert className="border-l-4 border-l-blue-600 bg-blue-500/5">
          <Info className="h-5 w-5 text-blue-600" />
          <AlertTitle className="font-bold text-blue-600">Warnings: Best Practice Recommendations ({warnings})</AlertTitle>
          <AlertDescription className="mt-2">
            <ul className="space-y-1 ml-4">
              {warningsList.slice(0, 3).map((warning: any, idx: number) => (
                <li key={idx} className="text-sm">
                  <span className="font-semibold">{warning.type}:</span> {warning.message}
                </li>
              ))}
            </ul>
            {warningsList.length > 3 && (
              <p className="text-xs mt-2 text-muted-foreground">+ {warningsList.length - 3} more warnings</p>
            )}
          </AlertDescription>
        </Alert>
      )}

      {totalIssues === 0 && warnings === 0 && (
        <Alert className="border-l-4 border-l-green-600 bg-green-500/5">
          <CheckCircle2 className="h-5 w-5 text-green-600" />
          <AlertTitle className="font-bold text-lg text-green-600">✓ Validation Passed</AlertTitle>
          <AlertDescription>
            All topology validation checks passed. Network architecture meets enterprise GPU cluster best practices.
          </AlertDescription>
        </Alert>
      )}

      {/* Export Button */}
      <div className="flex justify-end">
        <Button onClick={handleExportMatrix} disabled={isExporting} size="lg">
          <Download className="w-4 h-4 mr-2" />
          {isExporting ? 'Exporting...' : 'Export Cabling Matrix CSV'}
        </Button>
      </div>

      <Separator />

      {/* Device Breakdown */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Server className="w-5 h-5" />
          Devices by Type
        </h3>
        <div className="space-y-3">
          {Object.entries(devicesByType).map(([type, devices]) => (
            <div key={type} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {type === 'compute' && <Server className="w-4 h-4 text-blue-500" />}
                {type === 'storage' && <HardDrive className="w-4 h-4 text-purple-500" />}
                {type.includes('switch') && <Network className="w-4 h-4 text-green-500" />}
                <span className="capitalize font-medium">{type.replace('-', ' ')}</span>
              </div>
              <Badge variant="outline">{(devices as any[]).length} devices</Badge>
            </div>
          ))}
        </div>
      </Card>

      {/* Connection Breakdown */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Cable className="w-5 h-5" />
          Connections by Type
        </h3>
        <div className="space-y-3">
          {Object.entries(connectionsByType).map(([type, connections]) => (
            <div key={type} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div
                  className="w-4 h-4 rounded"
                  style={{
                    backgroundColor:
                      Object.keys(validationSummary).length > 0 ? '#3b82f6' : '#6b7280',
                  }}
                />
                <span className="font-medium">{type}</span>
              </div>
              <Badge variant="outline">{(connections as any[]).length} connections</Badge>
            </div>
          ))}
        </div>
      </Card>

      {/* Device List */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Extracted Devices</h3>
        <div className="max-h-96 overflow-y-auto">
          <div className="space-y-2">
            {results.devices.map((device) => (
              <div
                key={device.deviceId}
                className="p-3 bg-accent rounded-lg flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  {device.deviceType === 'compute' && <Server className="w-4 h-4" />}
                  {device.deviceType === 'storage' && <HardDrive className="w-4 h-4" />}
                  {device.deviceType?.includes('switch') && <Network className="w-4 h-4" />}
                  <div>
                    <p className="font-medium text-sm">{device.deviceName}</p>
                    <p className="text-xs text-muted-foreground">
                      {device.rackLocation} • {(device.ports as any[])?.length || 0} ports
                    </p>
                  </div>
                </div>
                <div className="text-xs">
                  <Badge variant="outline">
                    {device.deviceType}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {/* Connection Sample */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Connection Sample (First 20)</h3>
        <div className="max-h-96 overflow-y-auto">
          <div className="space-y-2">
            {results.connections.slice(0, 20).map((conn) => (
              <div key={conn.connectionId} className="p-3 bg-accent rounded-lg">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <p className="text-sm font-mono">
                      <span className="font-semibold">{conn.sourceDevice}</span>
                      <span className="text-muted-foreground">:{conn.sourcePort}</span>
                      <span className="mx-2">→</span>
                      <span className="font-semibold">{conn.destinationDevice}</span>
                      <span className="text-muted-foreground">:{conn.destinationPort}</span>
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {conn.connectionType} • {conn.bandwidth}
                      {conn.isTrunk && (
                        <div className="ml-2 text-xs">
                          <Badge variant="outline">
                            Trunk ({conn.trunkSize})
                          </Badge>
                        </div>
                      )}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
          {results.connections.length > 20 && (
            <p className="text-center text-sm text-muted-foreground mt-4">
              Showing 20 of {results.connections.length} connections. Export CSV for full list.
            </p>
          )}
        </div>
      </Card>
    </div>
  );
}
