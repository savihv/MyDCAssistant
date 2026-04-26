import React, { useState, useEffect } from "react";
import { format } from "date-fns";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../extensions/shadcn/components/table";
import { Badge } from "../extensions/shadcn/components/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../extensions/shadcn/components/card";
import { ScrollArea } from "../extensions/shadcn/components/scroll-area";
import { Button } from "../components/Button";
import { getFirestore, collection, query, orderBy, limit, onSnapshot } from "firebase/firestore";
import { firebaseApp } from "../app";

const db = getFirestore(firebaseApp);

export default function AuditLogViewer({ customerId }: { customerId: string }) {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!customerId) return;

    // Listen to real-time audit logs for the customer
    const q = query(
      collection(db, `customers/${customerId}/audit_logs`),
      orderBy("timestamp", "desc"),
      limit(100)
    );

    const unsubscribe = onSnapshot(q, (snapshot) => {
      const logData = snapshot.docs.map(doc => ({
        id: doc.id,
        ...doc.data()
      }));
      setLogs(logData);
      setLoading(false);
    });

    return () => unsubscribe();
  }, [customerId]);

  const getActionBadge = (action: string) => {
    if (action.includes("override")) return <Badge variant="outline">Manual Override</Badge>;
    if (action.includes("resolved")) return <Badge variant="default" className="bg-amber-600">Alert Resolved</Badge>;
    if (action.includes("provisioned")) return <Badge variant="default" className="bg-emerald-600">Provisioned</Badge>;
    return <Badge variant="outline">{action}</Badge>;
  };

  return (
    <Card className="w-full h-full border-gray-800 bg-black text-gray-100">
      <CardHeader className="pb-4">
        <div className="flex justify-between items-center">
          <div>
            <CardTitle className="text-xl font-bold font-mono text-cyan-400">SOC2 Audit Trail</CardTitle>
            <CardDescription className="text-gray-400">Immutable log of system provisioning actions.</CardDescription>
          </div>
          <Button variant="outline" className="border-cyan-800 text-cyan-400 hover:bg-cyan-950">
            Export CSV
          </Button>
        </div>
      </CardHeader>
      
      <CardContent>
        <ScrollArea className="h-[600px] w-full rounded-md border border-gray-800 p-1">
          {loading ? (
            <div className="flex justify-center items-center h-40">
              <span className="text-cyan-500 animate-pulse font-mono">Loading audit logs...</span>
            </div>
          ) : logs.length === 0 ? (
            <div className="text-center p-8 text-gray-500 font-mono">
              No audit logs found for this tenant.
            </div>
          ) : (
            <Table>
              <TableHeader className="bg-gray-900 border-b border-gray-800">
                <TableRow className="border-gray-800 hover:bg-transparent">
                  <TableHead className="text-gray-400 font-mono">Timestamp</TableHead>
                  <TableHead className="text-gray-400 font-mono">User</TableHead>
                  <TableHead className="text-gray-400 font-mono">Action</TableHead>
                  <TableHead className="text-gray-400 font-mono">Context</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((log) => (
                  <TableRow key={log.id} className="border-gray-800 hover:bg-gray-900/50">
                    <TableCell className="font-mono text-xs text-gray-500">
                      {log.datetimeIso ? format(new Date(log.datetimeIso), "yyyy-MM-dd HH:mm:ss") : "Unknown"}
                    </TableCell>
                    <TableCell className="font-medium text-gray-300">
                      {log.userEmail}
                    </TableCell>
                    <TableCell>
                      {getActionBadge(log.action)}
                    </TableCell>
                    <TableCell className="text-xs text-gray-400 font-mono">
                      <pre className="max-w-[300px] overflow-hidden text-ellipsis whitespace-nowrap bg-black p-1 rounded border border-gray-800">
                        {log.details ? JSON.stringify(log.details) : "{}"}
                      </pre>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
