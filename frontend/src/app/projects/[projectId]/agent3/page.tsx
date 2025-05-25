// /Users/batu/Desktop/Projects/scienceharvester-ai/frontend/src/app/projects/[projectId]/agent3/page.tsx:
'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Loader2 } from 'lucide-react';
import { EventSourcePolyfill } from 'event-source-polyfill';
import { useProjects } from '@/context/ProjectsContext'; // Import useProjects

const Spinner = ({ size = 16, className = '' }: { size?: number; className?: string }) => (
  <Loader2 style={{ width: size, height: size }} className={`animate-spin ${className}`} />
);

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function Agent3ReportPage() {
  const params = useParams();
  const { getProjectDetails } = useProjects(); // Get project details fetcher

  const [currentProjectId, setCurrentProjectId] = useState<string>('');
  
  const [isGenerating, setIsGenerating] = useState(false); // For report generation stream
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [markdownReport, setMarkdownReport] = useState<string | null>(null);
  const [isPdfReady, setIsPdfReady] = useState(false); 
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  const [streamLog, setStreamLog] = useState<string[]>([]);

  const [isPreloading, setIsPreloading] = useState(true);
  const [preloadError, setPreloadError] = useState<string | null>(null);
  const [projectName, setProjectName] = useState<string>('');


  const eventSourceRef = useRef<EventSourcePolyfill | null>(null);

  // Effect to set currentProjectId from URL
  useEffect(() => {
    const pid = typeof params.projectId === 'string' ? params.projectId : '';
    if (pid) {
      setCurrentProjectId(pid);
    }
  }, [params.projectId]);

  // Effect for preloading existing report
  useEffect(() => {
    if (!currentProjectId) {
      setIsPreloading(false); // No project ID, so not preloading
      return;
    }

    const preloadReport = async () => {
      setIsPreloading(true);
      setMarkdownReport(null); // Clear previous
      setPreloadError(null);
      setIsPdfReady(false);

      try {
        const projectDetails = await getProjectDetails(currentProjectId);
        setProjectName(projectDetails?.name || `Project ${currentProjectId}`);

        if (projectDetails && projectDetails.agent3_report_md_file) {
          setStreamLog(prev => [...prev, `Found existing MD report path: ${projectDetails.agent3_report_md_file}. Fetching content...`]);
          const response = await fetch(`${API_BASE_URL}/api/projects/${currentProjectId}/files?file_key=agent3_report_md_file`);
          if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Failed to fetch preloaded MD report: ${response.status} ${errorText.substring(0,150)}`);
          }
          const mdContent = await response.text(); // MD is text
          setMarkdownReport(mdContent);
          setIsPdfReady(true); // If MD exists, PDF can be generated/downloaded
          setStreamLog(prev => [...prev, "Successfully preloaded existing report."]);
        } else {
          setStreamLog(prev => [...prev, "No existing report found for this project. Ready to generate."]);
        }
      } catch (err: any) {
        console.error("Error preloading report:", err);
        setPreloadError(err.message || "Failed to load existing report data.");
        setStreamLog(prev => [...prev, `Error preloading report: ${err.message}`]);
      } finally {
        setIsPreloading(false);
      }
    };

    preloadReport();

  }, [currentProjectId, getProjectDetails]);


  // Cleanup EventSource on component unmount
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  const handleStartReportGeneration = useCallback(() => {
    if (!currentProjectId) {
      setGenerationError("Project ID is missing. Cannot generate report.");
      return;
    }

    eventSourceRef.current?.close();

    setIsGenerating(true);
    setGenerationError(null);
    setMarkdownReport(null); // Clear previous report before generating new one
    setIsPdfReady(false);
    setStreamLog(["Attempting to connect to report generation stream..."]);

    const streamApiUrl = `${API_BASE_URL}/api/agent3/report/stream?project_id=${encodeURIComponent(currentProjectId)}`;
    
    try {
      const es = new EventSourcePolyfill(streamApiUrl, { heartbeatTimeout: 180_000 }); // 3 min heartbeat
      eventSourceRef.current = es;

      es.onopen = () => {
        setStreamLog(prev => [...prev, "Connection opened. Waiting for report generation to start..."]);
      };

      es.onmessage = (event) => {
        const messageData = event.data as string;
        // setStreamLog(prev => [...prev, `Raw stream message: ${messageData.substring(0,100)}...`]);

        if (messageData.startsWith('__RESULT__')) {
          try {
            const payloadString = messageData.replace('__RESULT__', '');
            const result = JSON.parse(payloadString);
            setMarkdownReport(result.report_md);
            setIsPdfReady(true); 
            setStreamLog(prev => [...prev, "Report content received successfully."]);
            setIsGenerating(false);
            es.close();
          } catch (e) {
            console.error("Failed to parse __RESULT__ payload:", e, "Data:", messageData);
            setGenerationError("Failed to parse report data from stream.");
            setStreamLog(prev => [...prev, "Error: Failed to parse result payload."]);
            setIsGenerating(false);
            es.close();
          }
        } else if (messageData.startsWith('__ERROR__')) {
          const errorMessage = messageData.replace('__ERROR__', '').trim();
          setGenerationError(`Report generation error: ${errorMessage}`);
          setStreamLog(prev => [...prev, `Error from stream: ${errorMessage}`]);
          setIsGenerating(false);
          es.close();
        } else {
          setStreamLog(prev => [...prev, messageData]); // General progress message
        }
      };

      es.onerror = (err) => {
        console.error("EventSource error:", err);
        let errorMsg = 'Connection error with the report stream.';
        // Note: EventSource error objects are basic and don't typically carry HTTP status.
        setGenerationError(errorMsg);
        setStreamLog(prev => [...prev, `Stream connection failed. ${errorMsg}`]);
        setIsGenerating(false);
        es.close(); 
      };

    } catch (e) {
        console.error("Failed to initialize EventSource:", e);
        setGenerationError("Failed to connect to the report generation service.");
        setIsGenerating(false);
    }
  }, [currentProjectId, API_BASE_URL]);

  const handleDownloadPdf = useCallback(async () => {
    if (!currentProjectId || !isPdfReady || isDownloadingPdf) return;

    setIsDownloadingPdf(true);
    setGenerationError(null); // Clear generation error, this is a new action

    try {
      // Use a GET request to fetch the PDF if the backend is designed to serve it directly
      // or POST if it needs to trigger generation. Your backend uses POST.
      const pdfApiUrl = `${API_BASE_URL}/api/agent3/report/pdf`;
      const formData = new FormData(); // POST endpoint expects FormData
      formData.append('project_id', currentProjectId);

      const response = await fetch(pdfApiUrl, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        let errorDetail = `Server responded with ${response.status}.`;
        try {
            const errorJson = await response.json(); // Try to get detail from JSON error
            errorDetail = errorJson.detail || errorDetail;
        } catch (e) { /* Ignore if response is not JSON */ }
        throw new Error(`PDF download failed: ${errorDetail}`);
      }

      const blob = await response.blob();
      if (blob.type !== "application/pdf") {
        // The server might have sent an error message as JSON or text instead of a PDF
        const errorText = await blob.text(); // Attempt to read error text from blob
        console.error("Downloaded content was not PDF:", errorText);
        throw new Error(`Expected PDF, but received ${blob.type}. Server message: ${errorText.substring(0, 200)}`);
      }

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${currentProjectId}_report.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setStreamLog(prev => [...prev, "PDF download initiated."]);

    } catch (err: any) {
      console.error("PDF download error:", err);
      setGenerationError(err.message || 'An unknown error occurred during PDF download.');
    } finally {
      setIsDownloadingPdf(false);
    }
  }, [currentProjectId, isPdfReady, isDownloadingPdf, API_BASE_URL]);

  return (
    <div className="container mx-auto p-4 md:p-6 space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl font-semibold">Agent 3: Project Report Synthesis</CardTitle>
          <p className="text-sm text-muted-foreground">
            Project: {projectName || (currentProjectId ? `ID: ${currentProjectId}` : "Loading...")}
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {isPreloading ? (
             <div className="flex items-center space-x-2 text-gray-500">
                <Spinner size={16} className="mr-2" /> Loading existing report data...
             </div>
          ) : preloadError && !markdownReport ? ( // Show preload error only if no report is loaded
             <Alert>
                <AlertTitle>Preload Issue</AlertTitle>
                <AlertDescription>{preloadError}</AlertDescription>
             </Alert>
          ) : null}

          <Button onClick={handleStartReportGeneration} disabled={isGenerating || isPreloading || !currentProjectId}>
            {isGenerating ? (
              <><Spinner size={16} className="mr-2" /> Generating Report...</>
            ) : (
              markdownReport ? 'Re-generate Full Report' : 'Generate Full Report'
            )}
          </Button>

          {generationError && (
            <Alert variant="destructive" className="mt-4">
              <AlertTitle>Generation Error</AlertTitle>
              <AlertDescription>{generationError}</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {(isGenerating || streamLog.length > (markdownReport ? 0 : 1) ) && ( // Show log if generating or if there are non-initial logs
         <Card>
            <CardHeader><CardTitle className="text-lg">Generation Log</CardTitle></CardHeader>
            <CardContent>
                <pre className="text-xs bg-muted p-3 rounded-md max-h-60 overflow-y-auto whitespace-pre-wrap">
                    {streamLog.join('\n')}
                </pre>
            </CardContent>
         </Card>
      )}

      {markdownReport && !isGenerating && ( // Show report if MD exists and not currently generating
        <Card>
          <CardHeader className="flex flex-row justify-between items-center">
            <CardTitle className="text-xl">Generated Report</CardTitle>
            <Button
              onClick={handleDownloadPdf}
              disabled={!isPdfReady || isDownloadingPdf}
              variant="secondary"
            >
              {isDownloadingPdf ? (
                <><Spinner size={16} className="mr-2" /> Downloading PDF...</>
              ) : (
                'Download as PDF'
              )}
            </Button>
          </CardHeader>
          <CardContent>
            <article className="prose dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {markdownReport}
              </ReactMarkdown>
            </article>
          </CardContent>
        </Card>
      )}
       {!markdownReport && !isGenerating && !isPreloading && !preloadError && currentProjectId && streamLog.length <=1 && (
        <p className="text-muted-foreground mt-4 text-center">No report generated yet for this project. Click "Generate Full Report" to start.</p>
      )}
    </div>
  );
}