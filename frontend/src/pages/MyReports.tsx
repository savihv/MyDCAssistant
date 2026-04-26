import React from "react";
import { TechnicianReportsList } from "../components/TechnicianReportsList";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../extensions/shadcn/components/card";

export default function MyReports() {
  return (
    <div className="container mx-auto p-4 md:p-6 lg:p-8">
      <Card className="bg-gray-800 border-gray-700 text-white">
        <CardHeader>
          <CardTitle className="text-2xl font-bold text-blue-400">
            My Service Reports
          </CardTitle>
          <CardDescription className="text-gray-400">
            A list of all the troubleshooting reports you have filed, ordered from newest to oldest.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <TechnicianReportsList />
        </CardContent>
      </Card>
    </div>
  );
}
