/**
 * IP Allocation Dashboard - Pre-Deployment Conflict Detection
 * 
 * Visualizes NVIDIA-compliant GPU IP schema before ZTP generation:
 * - Shows /31 subnet allocations for all GPU pairs
 * - Highlights IP conflicts (duplicates, overlaps, mgmt collisions)
 * - Validates global IP uniqueness across Multi-SU clusters
 * - Exports clean IP tables for NetBox/IPAM import
 * 
 * Visual Design:
 * - Table view with color-coded conflict indicators
 * - Summary cards showing total IPs, conflicts, health status
 * - Export buttons for CSV download
 * - Grouped by rack/plane for easy scanning
 */

import React, { useEffect, useState } from 'react';
import { apiClient } from "../app";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../extensions/shadcn/components/card";
import { Badge } from "../extensions/shadcn/components/badge";
import { Button } from "../components/Button";
import { Alert, AlertDescription } from "../extensions/shadcn/components/alert";
import { 
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../extensions/shadcn/components/table";
import { 
  CheckCircle2, 
  XCircle, 
  AlertTriangle,
  Download,
  Network
} from 'lucide-react';
import { toast } from 'sonner';

interface IPAllocation {
  device: string;
  gpu_ip: string;
  switch_ip: string;
  subnet: string;
  plane: number;
  global_rack: number;
}

interface IPConflict {
  conflict_type: string;
  ip_address: string;
  device1: string;
  device2: string;
  severity: string;
  resolution: string;
}

interface IPPreview {
  total_ips: number;
  ip_allocations: IPAllocation[];
  conflicts: IPConflict[];
  status: string;
  summary: {
    total_conflicts: number;
    critical_conflicts: number;
    conflicts_by_type: {
      DUPLICATE_IP: number;
      OVERLAPPING_SUBNET: number;
      MGMT_DATA_COLLISION: number;
    };
  };
}

export interface Props {
  projectId: string;
}

export function IPAllocationDashboard({ projectId }: Props) {
  const [preview, setPreview] = useState<IPPreview | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedPlane, setSelectedPlane] = useState<number | null>(null);

  useEffect(() => {
    fetchIPPreview();
  }, [projectId]);

  const fetchIPPreview = async () => {
    try {
      const response = await apiClient.get_ip_allocation_preview({ projectId });
      const data = await response.json();
      setPreview(data);
      setIsLoading(false);
      
      if (data.status === 'CONFLICTS_FOUND') {
        toast.error(`${data.summary.total_conflicts} IP conflicts detected!`);
      } else {
        toast.success('No IP conflicts detected');
      }
    } catch (error) {
      console.error('Failed to fetch IP preview:', error);
      toast.error('Failed to load IP allocation preview');
    }
  };

  const exportToCSV = () => {
    if (!preview) return;
    
    const headers = ['Device', 'GPU IP', 'Switch IP', 'Subnet', 'Plane', 'Global Rack'];
    const rows = preview.ip_allocations.map(alloc => [
      alloc.device,
      alloc.gpu_ip,
      alloc.switch_ip,
      alloc.subnet,
      alloc.plane.toString(),
      alloc.global_rack.toString()
    ]);
    
    const csv = [headers, ...rows].map(row => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ip-allocation-${projectId}.csv`;
    a.click();
    
    toast.success('IP allocation table exported');
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'CRITICAL': return 'destructive';
      case 'HIGH': return 'destructive';
      case 'MEDIUM': return 'secondary';
      default: return 'outline';
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>IP Allocation Preview</CardTitle>
          <CardDescription>Scanning IP schema for conflicts...</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="animate-pulse space-y-4">
            <div className="h-32 bg-gray-200 dark:bg-gray-700 rounded" />
            <div className="h-64 bg-gray-200 dark:bg-gray-700 rounded" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!preview) return null;

  const filteredAllocations = selectedPlane !== null
    ? preview.ip_allocations.filter(a => a.plane === selectedPlane)
    : preview.ip_allocations;

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardDescription className="text-xs">Total IPs Allocated</CardDescription>
            <CardTitle className="text-3xl text-foreground">
              {preview.total_ips.toLocaleString()}
            </CardTitle>
          </CardHeader>
        </Card>

        <Card className={preview.status === 'CLEAN' ? 'border-green-500' : 'border-red-500'}>
          <CardHeader className="pb-3">
            <CardDescription className="text-xs">Schema Status</CardDescription>
            <CardTitle className="text-2xl flex items-center gap-2">
              {preview.status === 'CLEAN' ? (
                <>
                  <CheckCircle2 className="h-6 w-6 text-green-500" />
                  <span className="text-green-600 dark:text-green-400">CLEAN</span>
                </>
              ) : (
                <>
                  <XCircle className="h-6 w-6 text-red-500" />
                  <span className="text-red-600 dark:text-red-400">CONFLICTS</span>
                </>
              )}
            </CardTitle>
          </CardHeader>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardDescription className="text-xs">Total Conflicts</CardDescription>
            <CardTitle className="text-3xl text-foreground">
              {preview.summary.total_conflicts}
            </CardTitle>
          </CardHeader>
        </Card>

        <Card className="border-orange-500">
          <CardHeader className="pb-3">
            <CardDescription className="text-xs">Critical Issues</CardDescription>
            <CardTitle className="text-3xl text-orange-600 dark:text-orange-400">
              {preview.summary.critical_conflicts}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Conflicts Alert */}
      {preview.conflicts.length > 0 && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            <strong className="text-lg">🚨 IP Conflicts Detected</strong>
            <div className="mt-2 space-y-2">
              {Object.entries(preview.summary.conflicts_by_type).map(([type, count]) => (
                count > 0 && (
                  <div key={type} className="text-sm">
                    • {type.replace(/_/g, ' ')}: {count} conflict{count > 1 ? 's' : ''}
                  </div>
                )
              ))}
            </div>
          </AlertDescription>
        </Alert>
      )}

      {/* Conflict Details Table */}
      {preview.conflicts.length > 0 && (
        <Card className="border-red-500">
          <CardHeader>
            <CardTitle className="text-red-600 dark:text-red-400 flex items-center gap-2">
              <XCircle className="h-5 w-5" />
              Conflict Details
            </CardTitle>
            <CardDescription>Must resolve before ZTP generation</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>IP Address</TableHead>
                  <TableHead>Device 1</TableHead>
                  <TableHead>Device 2</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Resolution</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {preview.conflicts.map((conflict, index) => (
                  <TableRow key={index} className="bg-red-50 dark:bg-red-950">
                    <TableCell className="font-mono text-xs">
                      {conflict.conflict_type.replace(/_/g, ' ')}
                    </TableCell>
                    <TableCell className="font-mono text-sm font-medium">
                      {conflict.ip_address}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{conflict.device1}</TableCell>
                    <TableCell className="font-mono text-xs">{conflict.device2}</TableCell>
                    <TableCell>
                      <Badge variant={getSeverityColor(conflict.severity)}>
                        {conflict.severity}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs">{conflict.resolution}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* IP Allocation Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-foreground">
                <Network className="h-5 w-5" />
                IP Allocation Preview (Sample: First 100)
              </CardTitle>
              <CardDescription>
                NVIDIA-compliant /31 subnets for GPU-to-Switch point-to-point links
              </CardDescription>
            </div>
            <Button onClick={exportToCSV} variant="outline">
              <Download className="h-4 w-4 mr-2" />
              Export CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* Plane Filter */}
          <div className="mb-4 flex gap-2">
            <Button 
              size="sm" 
              variant={selectedPlane === null ? "default" : "outline"}
              onClick={() => setSelectedPlane(null)}
            >
              All Planes
            </Button>
            <Button 
              size="sm" 
              variant={selectedPlane === 0 ? "default" : "outline"}
              onClick={() => setSelectedPlane(0)}
            >
              Plane 0
            </Button>
            <Button 
              size="sm" 
              variant={selectedPlane === 1 ? "default" : "outline"}
              onClick={() => setSelectedPlane(1)}
            >
              Plane 1
            </Button>
          </div>

          <div className="border border-border rounded-md overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted">
                  <TableHead className="font-semibold">Device</TableHead>
                  <TableHead className="font-semibold">GPU IP</TableHead>
                  <TableHead className="font-semibold">Switch IP</TableHead>
                  <TableHead className="font-semibold">Subnet (/31)</TableHead>
                  <TableHead className="font-semibold">Plane</TableHead>
                  <TableHead className="font-semibold">Global Rack</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredAllocations.map((alloc, index) => (
                  <TableRow key={index}>
                    <TableCell className="font-mono text-xs text-foreground">
                      {alloc.device}
                    </TableCell>
                    <TableCell className="font-mono text-sm font-medium text-blue-600 dark:text-blue-400">
                      {alloc.gpu_ip}
                    </TableCell>
                    <TableCell className="font-mono text-sm font-medium text-green-600 dark:text-green-400">
                      {alloc.switch_ip}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {alloc.subnet}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">P{alloc.plane}</Badge>
                    </TableCell>
                    <TableCell className="text-foreground">{alloc.global_rack}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
