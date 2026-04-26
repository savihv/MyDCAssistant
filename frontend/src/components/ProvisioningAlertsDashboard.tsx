import React from "react";
import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { apiClient } from 'app';
import { toast } from 'sonner';
import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Server,
  MapPin,
  ShieldAlert,
  Package,
  Zap,
  Clock,
  User,
} from 'lucide-react';

interface ProvisioningAlert {
  alert_id: string;
  projectId: string;
  severity: string;
  type: string;
  status: string;
  location: {
    rack?: string;
    uPosition?: string;
    site?: string;
    room?: string;
  } | null;
  planned: {
    serialNumber?: string;
    model?: string;
    deviceName?: string;
    macAddress?: string;
  } | null;
  detected: {
    serialNumber?: string;
    model?: string;
    macAddress?: string;
  } | null;
  message: string;
  impact: string;
  recommendation: string;
  created_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution_action: string | null;
}

export interface Props {
  projectId: string;
}

export function ProvisioningAlertsDashboard({ projectId }: Props) {
  const [alerts, setAlerts] = useState<ProvisioningAlert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [resolvingAlertId, setResolvingAlertId] = useState<string | null>(null);
  const [showOverrideDialog, setShowOverrideDialog] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<ProvisioningAlert | null>(null);

  // Real-time polling every 5 seconds
  useEffect(() => {
    loadAlerts();
    const interval = setInterval(loadAlerts, 5000);
    return () => clearInterval(interval);
  }, [projectId]);

  const loadAlerts = async () => {
    try {
      const response = await apiClient.get_provisioning_alerts({ projectId });
      const data: ProvisioningAlert[] = (await response.json()) as any;
      
      // Show toast for new critical alerts
      if (data.length > alerts.length) {
        const newAlerts = data.filter(
          (alert) => !alerts.some((a) => a.alert_id === alert.alert_id)
        );
        newAlerts.forEach((alert) => {
          if (alert.severity === 'CRITICAL') {
            toast.error(`🚨 Critical Alert: ${alert.message}`);
          }
        });
      }

      setAlerts(data);
    } catch (error) {
      console.error('Failed to load alerts:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResolve = async (
    alertId: string,
    strategy: string,
    alert: ProvisioningAlert
  ) => {
    if (strategy === 'OVERRIDE_AND_PROCEED') {
      setSelectedAlert(alert);
      setShowOverrideDialog(true);
      return;
    }

    await executeResolve(alertId, strategy);
  };

  const executeResolve = async (alertId: string, strategy: string) => {
    setResolvingAlertId(alertId);
    try {
      const response = await apiClient.resolve_provisioning_alert({
        alert_id: alertId,
        strategy: strategy,
        resolved_by: 'installation-lead', // TODO: Get from auth context
      });

      const result = await response.json();

      if (result.status === 'success') {
        toast.success(result.message);
        await loadAlerts(); // Refresh alerts
      } else {
        toast.error('Resolution failed. Please try again.');
      }
    } catch (error) {
      toast.error('Failed to resolve alert. Please try again.');
      console.error('Resolve error:', error);
    } finally {
      setResolvingAlertId(null);
      setShowOverrideDialog(false);
      setSelectedAlert(null);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'CRITICAL':
        return 'bg-red-500 text-white';
      case 'HIGH':
        return 'bg-orange-500 text-white';
      case 'MEDIUM':
        return 'bg-yellow-500 text-black';
      default:
        return 'bg-gray-500 text-white';
    }
  };

  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'IDENTITY_MISMATCH':
        return <ShieldAlert className="w-5 h-5" />;
      case 'UNKNOWN_DEVICE':
        return <AlertTriangle className="w-5 h-5" />;
      case 'UNREACHABLE_SWITCH':
        return <XCircle className="w-5 h-5" />;
      default:
        return <AlertTriangle className="w-5 h-5" />;
    }
  };

  if (isLoading) {
    return (
      <Card className="p-8 text-center">
        <div className="flex items-center justify-center gap-2">
          <RefreshCw className="w-5 h-5 animate-spin" />
          <p className="text-muted-foreground">Loading provisioning alerts...</p>
        </div>
      </Card>
    );
  }

  if (alerts.length === 0) {
    return (
      <Card className="p-8">
        <div className="text-center space-y-4">
          <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto" />
          <div>
            <h3 className="text-xl font-semibold">All Clear</h3>
            <p className="text-muted-foreground mt-2">
              No active provisioning alerts. All switches are verified and ready.
            </p>
          </div>
          <Button onClick={loadAlerts} variant="outline" size="sm">
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Day 1 Provisioning Alerts</h2>
          <p className="text-muted-foreground">
            {alerts.length} active {alerts.length === 1 ? 'alert' : 'alerts'} requiring attention
          </p>
        </div>
        <Button onClick={loadAlerts} variant="outline" size="sm">
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Alerts List */}
      <div className="space-y-4">
        {alerts.map((alert) => (
          <Card key={alert.alert_id} className="p-6 border-2 border-red-200 dark:border-red-900">
            {/* Alert Header */}
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-start gap-3">
                <div className="p-2 bg-red-500/10 rounded">
                  {getAlertIcon(alert.type)}
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Badge className={getSeverityColor(alert.severity)}>
                      {alert.severity}
                    </Badge>
                    <Badge variant="outline">{alert.type.replace(/_/g, ' ')}</Badge>
                  </div>
                  <h3 className="text-lg font-semibold">{alert.message}</h3>
                </div>
              </div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Clock className="w-4 h-4" />
                {new Date(alert.created_at).toLocaleString()}
              </div>
            </div>

            {/* Location */}
            {alert.location && (
              <div className="mb-4 p-3 bg-muted rounded-lg">
                <div className="flex items-center gap-2 text-sm font-medium mb-1">
                  <MapPin className="w-4 h-4" />
                  Location
                </div>
                <p className="text-sm text-muted-foreground">
                  {alert.location.site && `${alert.location.site} > `}
                  {alert.location.room && `${alert.location.room} > `}
                  {alert.location.rack && `Rack ${alert.location.rack}`}
                  {alert.location.uPosition && ` / U${alert.location.uPosition}`}
                </p>
              </div>
            )}

            {/* Side-by-Side Comparison */}
            {alert.type === 'IDENTITY_MISMATCH' && alert.planned && alert.detected && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                {/* Expected (Planned) */}
                <div className="p-4 border-2 border-orange-200 dark:border-orange-900 rounded-lg">
                  <div className="flex items-center gap-2 mb-3">
                    <Package className="w-5 h-5 text-orange-500" />
                    <h4 className="font-semibold text-orange-700 dark:text-orange-400">
                      Expected (Day 0 Plan)
                    </h4>
                  </div>
                  <div className="space-y-2 text-sm">
                    {alert.planned.deviceName && (
                      <div>
                        <span className="font-medium">Device:</span>{' '}
                        <span className="text-muted-foreground">{alert.planned.deviceName}</span>
                      </div>
                    )}
                    {alert.planned.serialNumber && (
                      <div>
                        <span className="font-medium">Serial:</span>{' '}
                        <span className="font-mono text-muted-foreground">
                          {alert.planned.serialNumber}
                        </span>
                      </div>
                    )}
                    {alert.planned.model && (
                      <div>
                        <span className="font-medium">Model:</span>{' '}
                        <span className="text-muted-foreground">{alert.planned.model}</span>
                      </div>
                    )}
                    {alert.planned.macAddress && (
                      <div>
                        <span className="font-medium">MAC:</span>{' '}
                        <span className="font-mono text-muted-foreground">
                          {alert.planned.macAddress}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Detected (Reality) */}
                <div className="p-4 border-2 border-red-200 dark:border-red-900 rounded-lg">
                  <div className="flex items-center gap-2 mb-3">
                    <Server className="w-5 h-5 text-red-500" />
                    <h4 className="font-semibold text-red-700 dark:text-red-400">
                      Detected (Physical Reality)
                    </h4>
                  </div>
                  <div className="space-y-2 text-sm">
                    {alert.detected.serialNumber && (
                      <div>
                        <span className="font-medium">Serial:</span>{' '}
                        <span className="font-mono text-muted-foreground">
                          {alert.detected.serialNumber}
                        </span>
                      </div>
                    )}
                    {alert.detected.model && (
                      <div>
                        <span className="font-medium">Model:</span>{' '}
                        <span className="text-muted-foreground">{alert.detected.model}</span>
                      </div>
                    )}
                    {alert.detected.macAddress && (
                      <div>
                        <span className="font-medium">MAC:</span>{' '}
                        <span className="font-mono text-muted-foreground">
                          {alert.detected.macAddress}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Impact & Recommendation */}
            <div className="space-y-3 mb-4">
              <Alert variant="destructive">
                <Zap className="h-4 w-4" />
                <AlertDescription>
                  <span className="font-semibold">Impact:</span> {alert.impact}
                </AlertDescription>
              </Alert>

              <Alert>
                <AlertDescription>
                  <span className="font-semibold">Recommendation:</span> {alert.recommendation}
                </AlertDescription>
              </Alert>
            </div>

            {/* Resolution Actions */}
            <div className="flex flex-col sm:flex-row gap-3 pt-4 border-t">
              <Button
                onClick={() => handleResolve(alert.alert_id, 'SWAP_HARDWARE', alert)}
                disabled={resolvingAlertId === alert.alert_id}
                variant="outline"
                className="flex-1"
              >
                {resolvingAlertId === alert.alert_id ? (
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Package className="w-4 h-4 mr-2" />
                )}
                Mark for Physical Swap
              </Button>

              <Button
                onClick={() => handleResolve(alert.alert_id, 'UPDATE_INVENTORY', alert)}
                disabled={resolvingAlertId === alert.alert_id}
                variant="default"
                className="flex-1"
              >
                {resolvingAlertId === alert.alert_id ? (
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                )}
                Update Inventory to Match Reality
              </Button>

              <Button
                onClick={() => handleResolve(alert.alert_id, 'OVERRIDE_AND_PROCEED', alert)}
                disabled={resolvingAlertId === alert.alert_id}
                variant="outline"
                className="flex-1"
              >
                {resolvingAlertId === alert.alert_id ? (
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <ShieldAlert className="w-4 h-4 mr-2" />
                )}
                Override & Proceed
              </Button>
            </div>
          </Card>
        ))}
      </div>

      {/* Override Confirmation Dialog */}
      <AlertDialog open={showOverrideDialog} onOpenChange={setShowOverrideDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2 text-red-600">
              <ShieldAlert className="w-5 h-5" />
              Dangerous Override Action
            </AlertDialogTitle>
            <AlertDialogDescription className="space-y-3">
              <p className="font-semibold">
                ⚠️ You are about to proceed despite a hardware identity mismatch.
              </p>
              <p>
                This can lead to catastrophic errors such as:
              </p>
              <ul className="list-disc list-inside space-y-1 text-sm">
                <li>Wrong configuration pushed to hardware</li>
                <li>Network loops taking down the entire cluster</li>
                <li>Bricked devices requiring RMA</li>
                <li>8+ hours of troubleshooting</li>
              </ul>
              <p className="font-semibold mt-4">
                Are you absolutely sure you want to proceed?
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel - Do Not Override</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (selectedAlert) {
                  executeResolve(selectedAlert.alert_id, 'OVERRIDE_AND_PROCEED');
                }
              }}
              className="bg-red-600 hover:bg-red-700"
            >
              I Accept the Risk - Proceed
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
