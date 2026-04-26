import React, { useState, useEffect } from "react";
import { apiClient } from "../app";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { FileText, Calendar, MapPin } from "lucide-react";

export function TechnicianReportsList() {
  const [reports, setReports] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const loadReports = async () => {
      setIsLoading(true);
      setError(null);
      try {
        // This will call the new /my-reports endpoint
        const response = await apiClient.get_my_reports();
        if (response.ok) {
          const data = await response.json();
          // --- THE FIX ---
          // Before setting the state, check if 'data' is actually an array.
          // If the backend returned an error object or something else, this will prevent the crash.
          if (Array.isArray(data)) {
            setReports(data);
          } else {
            // If we didn't get an array, something went wrong.
            // We can default to an empty array to prevent the crash.
            setReports([]); 
            console.error("Backend did not return an array of reports:", data);
            setError("An error occurred while parsing reports.");
          }
        } else {
          // Handle non-OK responses (e.g., 500 Internal Server Error)
          const errorData = await response.json().catch(() => ({ detail: "An unknown error occurred." }));
          setError((errorData as any).detail || "Failed to fetch reports.");
          toast.error((errorData as any).detail || "Failed to fetch reports.");
        }
      } catch (err: any) {
        setError(err.message || "An unexpected error occurred.");
        toast.error("Could not load your reports.");
      } finally {
        setIsLoading(false);
      }
    };

    loadReports();
  }, []);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-40">
        <p className="text-gray-400">Loading reports...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex justify-center items-center h-40">
        <p className="text-red-500">{error}</p>
      </div>
    );
  }

  // When the user has no reports yet
  if (reports.length === 0) {
    return (
        <div className="text-center py-10 px-4 bg-gray-800 rounded-lg">
            <FileText className="mx-auto h-12 w-12 text-gray-500" />
            <h3 className="mt-4 text-lg font-medium text-white">No Reports Found</h3>
            <p className="mt-1 text-sm text-gray-400">
                You have not generated any service reports yet.
            </p>
        </div>
    );
  }

  return (
    <div className="space-y-4">
      {reports.map((report) => (
        <Card key={report.report_id} className="bg-gray-800 border-gray-700 text-white">
          <CardHeader>
            <CardTitle className="text-blue-400">Report for Session: {report.session_id}</CardTitle>
            <CardDescription className="flex items-center text-gray-400 pt-2">
              <Calendar className="w-4 h-4 mr-2" />
              Generated on: {new Date(report.created_at).toLocaleDateString()}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center text-gray-300 mb-4">
              <MapPin className="w-4 h-4 mr-2" />
              Location: {report.location}
            </div>
            {/* The button to view the full report can be implemented here */}
            {/* For now, we'll just show the details */}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
