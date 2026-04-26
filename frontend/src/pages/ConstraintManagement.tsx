import { useState, useEffect } from 'react';
import { useUserGuardContext } from "../app";
import { apiClient } from "../app";
import { Button } from "../components/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../extensions/shadcn/components/card";
import { Input } from "../extensions/shadcn/components/input";
import { Label } from "../extensions/shadcn/components/label";
import { Textarea } from "../extensions/shadcn/components/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../extensions/shadcn/components/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../extensions/shadcn/components/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../extensions/shadcn/components/table";
import { Badge } from "../extensions/shadcn/components/badge";
import { toast } from 'sonner';
import { Loader2, Plus, Edit, Trash2, Download, Filter, X } from 'lucide-react';
import type {
  ConstraintResponse,
  ConstraintCreate,
  ConstraintUpdate,
} from "../apiclient/data-contracts";

const DOMAINS = [
  { value: 'dcdc', label: 'Datacenter Deployment and Ops' },
  { value: 'media_entertainment', label: 'Media and Entertainment' },
  { value: 'healthcare', label: 'Healthcare Operations' },
  { value: 'finance', label: 'Financial Trading' },
  { value: 'manufacturing', label: 'Manufacturing' },
  { value: 'general', label: 'General/Other' },
];

const CATEGORIES = [
  { value: 'safety', label: 'Safety' },
  { value: 'compliance', label: 'Compliance' },
  { value: 'workflow', label: 'Workflow' },
  { value: 'equipment', label: 'Equipment' },
  { value: 'policy', label: 'Policy' },
];

const SEVERITIES = [
  { value: 'critical', label: 'Critical', color: 'destructive' },
  { value: 'warning', label: 'Warning', color: 'default' },
  { value: 'info', label: 'Info', color: 'secondary' },
] as const;

export default function ConstraintManagement() {
  const { user } = useUserGuardContext();
  const [constraints, setConstraints] = useState<ConstraintResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [editingConstraint, setEditingConstraint] = useState<ConstraintResponse | null>(null);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);

  // Filters
  const [filterDomain, setFilterDomain] = useState<string>('all');
  const [filterCategory, setFilterCategory] = useState<string>('all');
  const [filterSeverity, setFilterSeverity] = useState<string>('all');
  const [showActiveOnly, setShowActiveOnly] = useState(true);

  // Form state
  const [formData, setFormData] = useState<ConstraintCreate>({
    domain: 'dcdc',
    category: 'safety',
    severity: 'critical',
    rule: '',
    reasoning: '',
    source: '',
    active: true,
  });

  const loadConstraints = async () => {
    try {
      setLoading(true);
      const params: any = {};
      if (filterDomain && filterDomain !== 'all') params.domain = filterDomain;
      if (filterCategory && filterCategory !== 'all') params.category = filterCategory;
      if (filterSeverity && filterSeverity !== 'all') params.severity = filterSeverity;
      params.active_only = showActiveOnly;

      const response = await apiClient.list_constraints(params);
      const data = await response.json();
      setConstraints(data.constraints || []);
    } catch (error: any) {
      console.error('Failed to load constraints:', error);
      toast.error('Failed to load constraints');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConstraints();
  }, [filterDomain, filterCategory, filterSeverity, showActiveOnly]);

  const handleCreate = async () => {
    if (!formData.rule.trim()) {
      toast.error('Rule is required');
      return;
    }

    try {
      setSaving(true);
      const response = await apiClient.create_new_constraint(formData);
      if (response.ok) {
        toast.success('Constraint created successfully');
        setShowCreateDialog(false);
        resetForm();
        loadConstraints();
      } else {
        const error = await response.json();
        toast.error((error as any).detail || 'Failed to create constraint');
      }
    } catch (error: any) {
      console.error('Failed to create constraint:', error);
      toast.error('Failed to create constraint');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async () => {
    if (!editingConstraint) return;

    try {
      setSaving(true);
      const updateData: ConstraintUpdate = {
        domain: formData.domain,
        category: formData.category,
        severity: formData.severity,
        rule: formData.rule,
        reasoning: formData.reasoning,
        source: formData.source,
        active: formData.active,
      };

      const response = await apiClient.update_existing_constraint(
        { constraintId: editingConstraint.id },
        updateData
      );

      if (response.ok) {
        toast.success('Constraint updated successfully');
        setShowEditDialog(false);
        setEditingConstraint(null);
        resetForm();
        loadConstraints();
      } else {
        const error = await response.json();
        toast.error((error as any).detail || 'Failed to update constraint');
      }
    } catch (error: any) {
      console.error('Failed to update constraint:', error);
      toast.error('Failed to update constraint');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (constraint: ConstraintResponse) => {
    if (!confirm(`Are you sure you want to delete this constraint?\n\n"${constraint.rule}"`)) {
      return;
    }

    try {
      const response = await apiClient.delete_existing_constraint({ constraintId: constraint.id });
      if (response.ok) {
        toast.success('Constraint deleted successfully');
        loadConstraints();
      } else {
        const error = await response.json();
        toast.error((error as any).detail || 'Failed to delete constraint');
      }
    } catch (error: any) {
      console.error('Failed to delete constraint:', error);
      toast.error('Failed to delete constraint');
    }
  };

  const handleImportTemplates = async () => {
    try {
      setImporting(true);
      const response = await apiClient.import_constraint_templates({
        domain: 'dcdc',
        templateSet: 'dcdc',
        skipDuplicates: true,
      });

      if (response.ok) {
        const data = await response.json();
        toast.success(data.message || 'Templates imported successfully');
        setShowImportDialog(false);
        loadConstraints();
      }
      // Note: Brain client throws on non-2xx response, so we don't need else block here
    } catch (error: any) {
      console.error('Failed to import templates:', error);
      
      let errorMessage = 'Failed to import templates';
      // Try to extract error message from response object if it was thrown by brain client
      if (error && typeof error.json === 'function') {
        try {
          const errorData = await error.json();
          if (errorData.detail) {
            errorMessage = errorData.detail;
          }
        } catch (e) {
          // Failed to parse error JSON, use default message
        }
      }
      
      toast.error(errorMessage);
    } finally {
      setImporting(false);
    }
  };

  const openEditDialog = (constraint: ConstraintResponse) => {
    setEditingConstraint(constraint);
    setFormData({
      domain: constraint.domain,
      category: constraint.category,
      severity: constraint.severity,
      rule: constraint.rule,
      reasoning: constraint.reasoning || '',
      source: constraint.source || '',
      active: constraint.active,
    });
    setShowEditDialog(true);
  };

  const resetForm = () => {
    setFormData({
      domain: 'dcdc',
      category: 'safety',
      severity: 'critical',
      rule: '',
      reasoning: '',
      source: '',
      active: true,
    });
  };

  const getSeverityBadge = (severity: string) => {
    const config = SEVERITIES.find((s) => s.value === severity);
    return (
      <Badge variant={config?.color || 'default'}>
        {config?.label || severity}
      </Badge>
    );
  };

  const clearFilters = () => {
    setFilterDomain('all');
    setFilterCategory('all');
    setFilterSeverity('all');
    setShowActiveOnly(true);
  };

  const hasActiveFilters = filterDomain !== 'all' || filterCategory !== 'all' || filterSeverity !== 'all' || !showActiveOnly;

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Constraint Management</h1>
            <p className="text-muted-foreground mt-1">
              Manage domain-specific constraints and import pre-configured templates
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowImportDialog(true)}>
              <Download className="w-4 h-4 mr-2" />
              Import Templates
            </Button>
            <Button onClick={() => setShowCreateDialog(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Create Constraint
            </Button>
          </div>
        </div>

        {/* Filters */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Filter className="w-5 h-5" />
                  Filters
                </CardTitle>
                <CardDescription>Filter constraints by domain, category, or severity</CardDescription>
              </div>
              {hasActiveFilters && (
                <Button variant="ghost" size="sm" onClick={clearFilters}>
                  <X className="w-4 h-4 mr-2" />
                  Clear Filters
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <Label>Domain</Label>
                <Select value={filterDomain} onValueChange={setFilterDomain}>
                  <SelectTrigger>
                    <SelectValue placeholder="All domains" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All domains</SelectItem>
                    {DOMAINS.map((d) => (
                      <SelectItem key={d.value} value={d.value}>
                        {d.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label>Category</Label>
                <Select value={filterCategory} onValueChange={setFilterCategory}>
                  <SelectTrigger>
                    <SelectValue placeholder="All categories" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All categories</SelectItem>
                    {CATEGORIES.map((c) => (
                      <SelectItem key={c.value} value={c.value}>
                        {c.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label>Severity</Label>
                <Select value={filterSeverity} onValueChange={setFilterSeverity}>
                  <SelectTrigger>
                    <SelectValue placeholder="All severities" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All severities</SelectItem>
                    {SEVERITIES.map((s) => (
                      <SelectItem key={s.value} value={s.value}>
                        {s.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label>Status</Label>
                <Select
                  value={showActiveOnly ? 'active' : 'all'}
                  onValueChange={(v) => setShowActiveOnly(v === 'active')}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active only</SelectItem>
                    <SelectItem value="all">All constraints</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Constraints Table */}
        <Card>
          <CardHeader>
            <CardTitle>Constraints ({constraints.length})</CardTitle>
            <CardDescription>
              {hasActiveFilters
                ? 'Showing filtered results'
                : 'All active constraints'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
              </div>
            ) : constraints.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-muted-foreground">
                  No constraints found. Create one or import templates to get started.
                </p>
              </div>
            ) : (
              <div className="border rounded-lg">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Severity</TableHead>
                      <TableHead>Domain</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead className="w-[40%]">Rule</TableHead>
                      <TableHead>Source</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {constraints.map((constraint) => (
                      <TableRow key={constraint.id}>
                        <TableCell>{getSeverityBadge(constraint.severity)}</TableCell>
                        <TableCell className="capitalize">{constraint.domain}</TableCell>
                        <TableCell className="capitalize">{constraint.category}</TableCell>
                        <TableCell>
                          <div className="max-w-md">
                            <p className="font-medium text-sm">{constraint.rule}</p>
                            {constraint.reasoning && (
                              <p className="text-xs text-muted-foreground mt-1">
                                {constraint.reasoning}
                              </p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {constraint.source || '—'}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openEditDialog(constraint)}
                            >
                              <Edit className="w-4 h-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDelete(constraint)}
                            >
                              <Trash2 className="w-4 h-4 text-destructive" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Create Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create New Constraint</DialogTitle>
            <DialogDescription>
              Define a custom constraint for your domain-specific workflow.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Domain *</Label>
                <Select
                  value={formData.domain}
                  onValueChange={(v) => setFormData({ ...formData, domain: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DOMAINS.map((d) => (
                      <SelectItem key={d.value} value={d.value}>
                        {d.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label>Category *</Label>
                <Select
                  value={formData.category}
                  onValueChange={(v) => setFormData({ ...formData, category: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CATEGORIES.map((c) => (
                      <SelectItem key={c.value} value={c.value}>
                        {c.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label>Severity *</Label>
              <Select
                value={formData.severity}
                onValueChange={(v) => setFormData({ ...formData, severity: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SEVERITIES.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label>Rule *</Label>
              <Textarea
                placeholder="Enter the constraint rule (e.g., 'PDUs must be installed before servers')"
                value={formData.rule}
                onChange={(e) => setFormData({ ...formData, rule: e.target.value })}
                rows={3}
              />
            </div>

            <div>
              <Label>Reasoning</Label>
              <Textarea
                placeholder="Explain why this constraint exists"
                value={formData.reasoning}
                onChange={(e) => setFormData({ ...formData, reasoning: e.target.value })}
                rows={2}
              />
            </div>

            <div>
              <Label>Source</Label>
              <Input
                placeholder="e.g., 'OSHA 1910.333', 'Company SOP'"
                value={formData.source}
                onChange={(e) => setFormData({ ...formData, source: e.target.value })}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={saving}>
              {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Create Constraint
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Constraint</DialogTitle>
            <DialogDescription>
              Update constraint details.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Domain *</Label>
                <Select
                  value={formData.domain}
                  onValueChange={(v) => setFormData({ ...formData, domain: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DOMAINS.map((d) => (
                      <SelectItem key={d.value} value={d.value}>
                        {d.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label>Category *</Label>
                <Select
                  value={formData.category}
                  onValueChange={(v) => setFormData({ ...formData, category: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CATEGORIES.map((c) => (
                      <SelectItem key={c.value} value={c.value}>
                        {c.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label>Severity *</Label>
              <Select
                value={formData.severity}
                onValueChange={(v) => setFormData({ ...formData, severity: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SEVERITIES.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label>Rule *</Label>
              <Textarea
                placeholder="Enter the constraint rule"
                value={formData.rule}
                onChange={(e) => setFormData({ ...formData, rule: e.target.value })}
                rows={3}
              />
            </div>

            <div>
              <Label>Reasoning</Label>
              <Textarea
                placeholder="Explain why this constraint exists"
                value={formData.reasoning}
                onChange={(e) => setFormData({ ...formData, reasoning: e.target.value })}
                rows={2}
              />
            </div>

            <div>
              <Label>Source</Label>
              <Input
                placeholder="e.g., 'OSHA 1910.333', 'Company SOP'"
                value={formData.source}
                onChange={(e) => setFormData({ ...formData, source: e.target.value })}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdate} disabled={saving}>
              {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Update Constraint
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Import Templates Dialog */}
      <Dialog open={showImportDialog} onOpenChange={setShowImportDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Import DCDC Templates</DialogTitle>
            <DialogDescription>
              Import 32 pre-configured constraints for Data Center Deployment & Commissioning.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="border border-border rounded-lg p-4 bg-muted/50">
              <h4 className="font-medium mb-2">Template Set: DCDC v1.0</h4>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• 32 total constraints</li>
                <li>• 15 Critical (safety & compliance)</li>
                <li>• 12 Warning (best practices)</li>
                <li>• 5 Info (helpful context)</li>
                <li>• Covers: Safety, Compliance, Workflow, Equipment, Policy</li>
              </ul>
            </div>

            <p className="text-sm text-muted-foreground">
              Duplicates will be automatically skipped based on rule text matching.
            </p>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowImportDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleImportTemplates} disabled={importing}>
              {importing && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Import Templates
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
