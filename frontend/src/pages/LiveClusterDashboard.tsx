/**
 * Live Cluster Provisioning Dashboard
 * 
 * The "Visual Source of Truth" for Installation Leads managing Day 0 → Day 1 transitions.
 * 
 * **The Critical Problem:**
 * In a 4,000 GPU cluster with 256 switches, you cannot "test" your way through CSVs.
 * You need to see the Delta between what was Planned (Day 0) and what is Live (Day 1).
 * 
 * **This Dashboard Shows:**
 * - 8-Rail SU Heatmap: Racks (rows) × Planes (columns) color-coded status grid
 * - Real-time provisioning status: PLANNED → DISCOVERY → CONFIGURING → VALIDATING → OPERATIONAL
 * - Cabling validation errors: Click red cell to see port-level mis-wires
 * - Stage gate controls: "Release Compute Nodes" button disabled until fabric >95% healthy
 * 
 * **Color Code:**
 * - Grey: Device in inventory, not yet seen on network
 * - Blue: Stage 1 discovery script executing
 * - Yellow: Stage 2 ZTP in progress (8-rail IP matrix being pushed)
 * - Purple: LLDP validation comparing actual wiring to GPU-to-Leaf mapper
 * - Green: Full match, BGP up, 800G links clean
 * - Red: Identity mismatch or wiring topology violation
 */

import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../extensions/shadcn/components/card";
import { Alert, AlertDescription } from "../extensions/shadcn/components/alert";
import { Button } from "../components/Button";
import { Badge } from "../extensions/shadcn/components/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../extensions/shadcn/components/tabs";
import { AlertCircle, CheckCircle2, Clock, Loader2, Network, Shield, Zap, RefreshCw } from 'lucide-react';
import { SUFabricHeatmap } from '../components/SUFabricHeatmap';
import { CablingDetailPane } from '../components/CablingDetailPane';
import { useFirestoreLiveData } from '../utils/useFirestoreLiveData';

interface SelectedSwitch {
  switchId: string;
  planeId: number;
  leafId: number;
  rackId: number;
  status: string;
}

export default function LiveClusterDashboard() {
  const [selectedSwitch, setSelectedSwitch] = useState<SelectedSwitch | null>(null);
  const [selectedSU, setSelectedSU] = useState<number>(1); // Default to SU-1
  
  // Real-time Firestore data
  const { 
    switches, 
    fabricHealth, 
    isLoading, 
    error,
    refreshData 
  } = useFirestoreLiveData();

  // Handle cell click in heatmap
  const handleSwitchSelect = (switchData: SelectedSwitch) => {
    setSelectedSwitch(switchData);
  };

  // Close detail pane
  const handleCloseDetail = () => {
    setSelectedSwitch(null);
  };

  // Stage gate: Release compute nodes
  const handleReleaseCompute = () => {
    if (fabricHealth.healthPercentage < 95) {
      alert('Cannot release compute nodes. Fabric health must be >95%');
      return;
    }
    // TODO: Implement release logic
    console.log('Releasing compute nodes...');
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center space-y-4">
          <Loader2 className="h-12 w-12 animate-spin mx-auto text-blue-500" />
          <p className="text-muted-foreground">Loading cluster provisioning status...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Failed to load cluster data: {error}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Live Cluster Provisioning</h1>
          <p className="text-muted-foreground mt-1">
            Real-time Day 0 → Day 1 transition monitoring
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button onClick={refreshData} variant="outline" size="sm">
            <Clock className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button 
            onClick={handleReleaseCompute}
            disabled={fabricHealth.healthPercentage < 95}
            className="bg-green-600 hover:bg-green-700"
          >
            <Zap className="h-4 w-4 mr-2" />
            Release Compute Nodes
            {fabricHealth.healthPercentage < 95 && (
              <Badge variant="outline" className="ml-2">
                {fabricHealth.healthPercentage.toFixed(1)}%
              </Badge>
            )}
          </Button>
        </div>
      </div>

      {/* Health Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Fabric Health</CardTitle>
            <Network className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {fabricHealth.healthPercentage.toFixed(1)}%
            </div>
            <p className="text-xs text-muted-foreground">
              {fabricHealth.operational} / {fabricHealth.total} switches operational
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Operational</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {fabricHealth.operational}
            </div>
            <p className="text-xs text-muted-foreground">
              Cabling verified, BGP up
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">In Progress</CardTitle>
            <Loader2 className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">
              {fabricHealth.inProgress}
            </div>
            <p className="text-xs text-muted-foreground">
              Discovery + ZTP + Validation
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Errors</CardTitle>
            <AlertCircle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {fabricHealth.errors}
            </div>
            <p className="text-xs text-muted-foreground">
              Identity/wiring mismatches
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Stage Gate Alert */}
      {fabricHealth.healthPercentage < 95 && (
        <Alert>
          <Shield className="h-4 w-4" />
          <AlertDescription>
            <strong>Stage Gate Active:</strong> Compute node release is blocked until fabric health reaches 95%. 
            Current: {fabricHealth.healthPercentage.toFixed(1)}% ({fabricHealth.errors} errors remaining)
          </AlertDescription>
        </Alert>
      )}

      {/* Main Content: SU Fabric Heatmap */}
      <Card>
        <CardHeader>
          <CardTitle>Scalable Unit Fabric Heatmap</CardTitle>
          <CardDescription>
            8-Rail topology view: Racks (rows) × Planes (columns). Click any cell for port-level details.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* SU Selector Tabs */}
          <Tabs value={`su-${selectedSU}`} onValueChange={(v) => setSelectedSU(parseInt(v.split('-')[1]))}>
            <TabsList className="mb-4">
              <TabsTrigger value="su-1">SU-1</TabsTrigger>
              <TabsTrigger value="su-2">SU-2</TabsTrigger>
              <TabsTrigger value="su-3">SU-3</TabsTrigger>
              <TabsTrigger value="su-4">SU-4</TabsTrigger>
            </TabsList>

            <TabsContent value={`su-${selectedSU}`} className="space-y-4">
              <SUFabricHeatmap
                suNumber={selectedSU}
                switches={switches}
                onSwitchSelect={handleSwitchSelect}
                selectedSwitch={selectedSwitch}
              />
            </TabsContent>
          </Tabs>

          {/* Status Legend */}
          <div className="mt-6 pt-4 border-t">
            <h4 className="text-sm font-semibold mb-3">Status Legend</h4>
            <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-gray-300" />
                <span className="text-xs">Planned</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-blue-500" />
                <span className="text-xs">Discovery</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-yellow-500" />
                <span className="text-xs">Configuring</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-purple-500" />
                <span className="text-xs">Validating</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-green-500" />
                <span className="text-xs">Operational</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-red-500" />
                <span className="text-xs">Error</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Cabling Detail Pane (Slide-out) */}
      {selectedSwitch && (
        <CablingDetailPane
          switchData={selectedSwitch}
          onClose={handleCloseDetail}
        />
      )}
    </div>
  );
}
