import React from "react";
import { useState } from 'react';
import { Button } from "../components/Button";
import { Input } from "../extensions/shadcn/components/input";
import { Label } from "../extensions/shadcn/components/label";
import { Checkbox } from "../extensions/shadcn/components/checkbox";
import { Card } from "../extensions/shadcn/components/card";
import { Plus, X, Loader2 } from 'lucide-react';
import { apiClient } from "../app";
import { toast } from 'sonner';

interface ColorLegendEntry {
  color: string;
  connectionType: string;
  bandwidth: string;
}

export interface Props {
  projectId: string;
  onComplete: () => void;
}

export function LegendConfiguration({ projectId, onComplete }: Props) {
  const [colorLegend, setColorLegend] = useState<ColorLegendEntry[]>([
    { color: '#0000FF', connectionType: 'InfiniBand (NDR)', bandwidth: '400G' },
    { color: '#FF0000', connectionType: 'Ethernet (Management)', bandwidth: '100G' },
  ]);

  const [deviceConventions, setDeviceConventions] = useState({
    computePrefix: 'Compute-Rack',
    storagePrefix: 'Storage-Array',
    switchLeafPrefix: 'Switch-Leaf',
    switchSpinePrefix: 'Switch-Spine',
  });

  const [processingConfig, setProcessingConfig] = useState({
    autoExpandTrunks: true,
    validateRailAlignment: true,
    spotCheckSampleSize: 5,
  });

  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    // Validation
    if (colorLegend.length === 0) {
      toast.error('Please add at least one connection type');
      return;
    }

    const hasEmptyFields = colorLegend.some(
      (entry) => !entry.connectionType || !entry.bandwidth
    );
    if (hasEmptyFields) {
      toast.error('Please fill in all connection type fields');
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await apiClient.configure_schematic_processing({
        projectId: projectId,
        project_id: projectId,
        color_legend: colorLegend,
        device_conventions: deviceConventions,
        processing_config: processingConfig,
      } as any);

      // apiClient natively throws on non-200 responses and returns the parsed JSON directly for 200 OK.
      const resAny = response as any;
      const data = resAny.data ? resAny.data : (resAny.json ? await resAny.json() : resAny);
      
      if (data && (data.status === 'processing_started' || data.project_id)) {
        toast.success('Processing started');
        onComplete();
      } else {
        toast.error(`Failed to start processing: Unexpected response format`);
      }
    } catch (error: any) {
      const errorDetail = error?.error?.detail || error?.message || 'Unknown error';
      toast.error(`Failed to start processing. ${errorDetail}`);
      console.error('Configuration error:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const addColorEntry = () => {
    setColorLegend([...colorLegend, { color: '#000000', connectionType: '', bandwidth: '' }]);
  };

  const removeColorEntry = (index: number) => {
    setColorLegend(colorLegend.filter((_, i) => i !== index));
  };

  const updateColorEntry = (index: number, field: keyof ColorLegendEntry, value: string) => {
    const updated = [...colorLegend];
    updated[index] = { ...updated[index], [field]: value };
    setColorLegend(updated);
  };

  return (
    <div className="space-y-8">
      {/* Color Legend Section */}
      <div>
        <h3 className="text-xl font-semibold mb-3">Connection Color Legend</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Define what each line color in your schematic represents. This helps the AI accurately
          identify different network types.
        </p>

        <div className="space-y-3">
          {colorLegend.map((entry, index) => (
            <Card key={index} className="p-4">
              <div className="flex gap-3 items-start">
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Color</Label>
                  <input
                    type="color"
                    value={entry.color}
                    onChange={(e) => updateColorEntry(index, 'color', e.target.value)}
                    className="w-16 h-10 rounded border border-border cursor-pointer"
                  />
                </div>

                <div className="flex-1 flex flex-col gap-1">
                  <Label className="text-xs">Connection Type</Label>
                  <Input
                    placeholder="e.g., InfiniBand (NDR)"
                    value={entry.connectionType}
                    onChange={(e) => updateColorEntry(index, 'connectionType', e.target.value)}
                  />
                </div>

                <div className="w-32 flex flex-col gap-1">
                  <Label className="text-xs">Bandwidth</Label>
                  <Input
                    placeholder="e.g., 400G"
                    value={entry.bandwidth}
                    onChange={(e) => updateColorEntry(index, 'bandwidth', e.target.value)}
                  />
                </div>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeColorEntry(index)}
                  className="mt-5"
                  disabled={colorLegend.length === 1}
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </Card>
          ))}

          <Button variant="outline" onClick={addColorEntry} className="w-full">
            <Plus className="w-4 h-4 mr-2" />
            Add Connection Type
          </Button>
        </div>
      </div>

      {/* Device Naming Conventions */}
      <div>
        <h3 className="text-xl font-semibold mb-3">Device Naming Conventions</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Specify the prefixes used in your schematic to identify different device types.
        </p>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label>Compute Node Prefix</Label>
            <Input
              value={deviceConventions.computePrefix}
              onChange={(e) =>
                setDeviceConventions({ ...deviceConventions, computePrefix: e.target.value })
              }
              placeholder="Compute-Rack"
            />
          </div>
          <div>
            <Label>Storage Prefix</Label>
            <Input
              value={deviceConventions.storagePrefix}
              onChange={(e) =>
                setDeviceConventions({ ...deviceConventions, storagePrefix: e.target.value })
              }
              placeholder="Storage-Array"
            />
          </div>
          <div>
            <Label>Leaf Switch Prefix</Label>
            <Input
              value={deviceConventions.switchLeafPrefix}
              onChange={(e) =>
                setDeviceConventions({ ...deviceConventions, switchLeafPrefix: e.target.value })
              }
              placeholder="Switch-Leaf"
            />
          </div>
          <div>
            <Label>Spine Switch Prefix</Label>
            <Input
              value={deviceConventions.switchSpinePrefix}
              onChange={(e) =>
                setDeviceConventions({ ...deviceConventions, switchSpinePrefix: e.target.value })
              }
              placeholder="Switch-Spine"
            />
          </div>
        </div>
      </div>

      {/* Processing Options */}
      <div>
        <h3 className="text-xl font-semibold mb-3">Processing Options</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Configure how the schematic should be analyzed and validated.
        </p>

        <div className="space-y-4">
          <div className="flex items-center space-x-3">
            <Checkbox
              id="expandTrunks"
              checked={processingConfig.autoExpandTrunks}
              onCheckedChange={(checked) =>
                setProcessingConfig({ ...processingConfig, autoExpandTrunks: !!checked })
              }
            />
            <Label htmlFor="expandTrunks" className="font-normal cursor-pointer">
              Auto-expand trunk lines into individual connections
            </Label>
          </div>

          <div className="flex items-center space-x-3">
            <Checkbox
              id="validateRails"
              checked={processingConfig.validateRailAlignment}
              onCheckedChange={(checked) =>
                setProcessingConfig({ ...processingConfig, validateRailAlignment: !!checked })
              }
            />
            <Label htmlFor="validateRails" className="font-normal cursor-pointer">
              Validate GPU rail alignment (best practices check)
            </Label>
          </div>

          <div className="flex items-center gap-3">
            <Label className="w-48">Spot-check sample size:</Label>
            <Input
              type="number"
              min={1}
              max={20}
              value={processingConfig.spotCheckSampleSize}
              onChange={(e) =>
                setProcessingConfig({
                  ...processingConfig,
                  spotCheckSampleSize: parseInt(e.target.value) || 5,
                })
              }
              className="w-24"
            />
            <span className="text-sm text-muted-foreground">connections to verify manually</span>
          </div>
        </div>
      </div>

      {/* Submit Button */}
      <div className="pt-4">
        <Button onClick={handleSubmit} size="lg" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Starting Processing...
            </>
          ) : (
            'Start Processing Schematic'
          )}
        </Button>
      </div>
    </div>
  );
}
