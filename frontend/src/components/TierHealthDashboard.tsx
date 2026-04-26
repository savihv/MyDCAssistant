/**
 * Tier Health Dashboard - Real-Time Cluster Readiness Monitor
 * 
 * Shows Installation Lead the global state machine status:
 * - BACKEND_FABRIC: Network switches (must be 100% before storage)
 * - STORAGE: NFS/Lustre nodes (must be ready before compute)
 * - COMPUTE: GPU nodes (only boots when all deps green)
 * 
 * Visual Design:
 * - Traffic light colors (Red → Yellow → Green)
 * - Dependency flow diagram (arrows showing tier order)
 * - Real-time polling (every 3 seconds)
 * - Emergency override controls for CTO
 */

import React, { useEffect, useState } from 'react';
import { apiClient } from 'app';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  CheckCircle2, 
  XCircle, 
  Clock, 
  AlertTriangle,
  ArrowRight,
  Shield
} from 'lucide-react';
import { toast } from 'sonner';

interface TierHealthData {
  health: string;
  total_devices: number;
  operational_devices: number;
  percentage: number;
  blocking_reason?: string;
}

interface TierReadiness {
  health: TierHealthData;
  dependencies: {
    allowed: boolean;
    blocking_tiers: Array<{
      tier: string;
      reason: string;
      percentage: number;
    }>;
    message: string;
  };
  can_provision: boolean;
}

interface ClusterReadiness {
  timestamp: string;
  tiers: {
    BACKEND_FABRIC: TierReadiness;
    STORAGE: TierReadiness;
    COMPUTE: TierReadiness;
  };
}

export interface Props {
  projectId: string;
}

export function TierHealthDashboard({ projectId }: Props) {
  const [readiness, setReadiness] = useState<ClusterReadiness | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showOverrideDialog, setShowOverrideDialog] = useState(false);
  const [overrideToken, setOverrideToken] = useState('');

  useEffect(() => {
    fetchReadiness();
    const interval = setInterval(fetchReadiness, 3000);
    return () => clearInterval(interval);
  }, [projectId]);

  const fetchReadiness = async () => {
    try {
      const response = await apiClient.get_cluster_readiness({ projectId });
      const data = await response.json();
      setReadiness(data);
      setIsLoading(false);
    } catch (error) {
      console.error('Failed to fetch cluster readiness:', error);
      toast.error('Failed to load cluster status');
    }
  };

  const getHealthIcon = (health: string) => {
    switch (health) {
      case 'READY':
        return <CheckCircle2 className="h-6 w-6 text-green-500" />;
      case 'IN_PROGRESS':
        return <Clock className="h-6 w-6 text-yellow-500" />;
      case 'BLOCKED':
        return <XCircle className="h-6 w-6 text-red-500" />;
      case 'NOT_STARTED':
        return <AlertTriangle className="h-6 w-6 text-gray-400" />;
      default:
        return <AlertTriangle className="h-6 w-6 text-gray-400" />;
    }
  };

  const getHealthColor = (health: string) => {
    switch (health) {
      case 'READY': return 'bg-green-500';
      case 'IN_PROGRESS': return 'bg-yellow-500';
      case 'BLOCKED': return 'bg-red-500';
      case 'NOT_STARTED': return 'bg-gray-400';
      default: return 'bg-gray-400';
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Cluster Readiness</CardTitle>
          <CardDescription>Loading tier health status...</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="animate-pulse space-y-4">
            <div className="h-24 bg-gray-200 dark:bg-gray-700 rounded" />
            <div className="h-24 bg-gray-200 dark:bg-gray-700 rounded" />
            <div className="h-24 bg-gray-200 dark:bg-gray-700 rounded" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!readiness) return null;

  const tiers = [
    { key: 'BACKEND_FABRIC', label: 'Backend Fabric', description: 'InfiniBand & High-Speed Ethernet' },
    { key: 'STORAGE', label: 'Storage Layer', description: 'NFS, Lustre, Ceph Nodes' },
    { key: 'COMPUTE', label: 'Compute Nodes', description: 'GPU Servers' }
  ];

  return (
    <div className="space-y-6">
      <Card className="border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-foreground">
            <Shield className="h-5 w-5" />
            Cluster Readiness - Tier Sequencing
          </CardTitle>
          <CardDescription>
            Real-time dependency validation ensures infrastructure tiers boot in correct order
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Tier Flow Diagram */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {tiers.map((tier, index) => {
          const tierData = readiness.tiers[tier.key as keyof typeof readiness.tiers];
          const health = tierData.health;
          const canProvision = tierData.can_provision;

          return (
            <React.Fragment key={tier.key}>
              <Card className={`border-2 ${canProvision ? 'border-green-500' : 'border-border'}`}>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {getHealthIcon(health.health)}
                      <div>
                        <CardTitle className="text-lg text-foreground">{tier.label}</CardTitle>
                        <CardDescription className="text-xs">{tier.description}</CardDescription>
                      </div>
                    </div>
                    <Badge variant={canProvision ? "default" : "destructive"}>
                      {canProvision ? "READY" : "BLOCKED"}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {/* Progress Bar */}
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-muted-foreground">Operational</span>
                      <span className="font-medium text-foreground">
                        {health.operational_devices} / {health.total_devices}
                      </span>
                    </div>
                    <Progress 
                      value={health.percentage} 
                      className="h-2"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      {health.percentage.toFixed(1)}% ready
                    </p>
                  </div>

                  {/* Blocking Reasons */}
                  {!canProvision && tierData.dependencies.blocking_tiers.length > 0 && (
                    <Alert variant="destructive">
                      <AlertTriangle className="h-4 w-4" />
                      <AlertDescription className="text-xs">
                        <strong>Blocked by:</strong>
                        <ul className="mt-1 space-y-1">
                          {tierData.dependencies.blocking_tiers.map((blocker, i) => (
                            <li key={i}>
                              {blocker.tier}: {blocker.reason}
                            </li>
                          ))}
                        </ul>
                      </AlertDescription>
                    </Alert>
                  )}

                  {/* Success Message */}
                  {canProvision && (
                    <Alert className="bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800">
                      <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
                      <AlertDescription className="text-xs text-green-800 dark:text-green-200">
                        All dependencies met. Provisioning allowed.
                      </AlertDescription>
                    </Alert>
                  )}
                </CardContent>
              </Card>

              {/* Arrow between tiers */}
              {index < tiers.length - 1 && (
                <div className="hidden md:flex items-center justify-center">
                  <ArrowRight className="h-8 w-8 text-gray-400" />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Emergency Override Controls */}
      <Card className="border-orange-500 border-2">
        <CardHeader>
          <CardTitle className="text-orange-600 dark:text-orange-400 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Emergency Override Controls
          </CardTitle>
          <CardDescription>
            CTO-level authorization required. Creates permanent audit trail.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>
              <strong>WARNING:</strong> Overriding tier dependencies can cause power storms,
              network flooding, and cluster-wide failures. Only use in emergency situations
              with CTO approval.
            </AlertDescription>
          </Alert>
          <Button 
            variant="outline" 
            onClick={() => setShowOverrideDialog(true)}
            disabled={!readiness.tiers.BACKEND_FABRIC.can_provision}
          >
            <Shield className="h-4 w-4 mr-2" />
            Activate Emergency Override
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
