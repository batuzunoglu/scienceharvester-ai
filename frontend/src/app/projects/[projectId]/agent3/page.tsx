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
      } catch (err: unknown) { 
        console.error("Error preloading report:", err);
        let errorMessage = "Failed to load existing report data.";
        if (err instanceof Error) {
            errorMessage = err.message;
        } else if (typeof err === 'string') {
            errorMessage = err;
        }
        setPreloadError(errorMessage);
        setStreamLog(prev => [...prev, `Error preloading report: ${errorMessage}`]);
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

        if (messageData.startsWith('__RESULT__')) {
          try {
            const payloadString = messageData.replace('__RESULT__', '');
            const result = JSON.parse(payloadString);
            setMarkdownReport(result.report_md);
            setIsPdfReady(true); 
            setStreamLog(prev => [...prev, "Report content received successfully."]);
            setIsGenerating(false);
            es.close();
          } catch (e: unknown) { 
            console.error("Failed to parse __RESULT__ payload:", e, "Data:", messageData);
            // FIX: 'parseErrorMsg' is never reassigned. Use 'const' instead.
            const parseErrorMsg = "Failed to parse report data from stream.";
            // if (e instanceof Error) { // This part was commented, making parseErrorMsg effectively const
            //   // parseErrorMsg = `Failed to parse report data: ${e.message}`; 
            // }
            setGenerationError(parseErrorMsg);
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
          setStreamLog(prev => [...prev, messageData]); 
        }
      };

      es.onerror = (errEvent) => { 
        console.error("EventSource error:", errEvent);
        const errorMsg = 'Connection error with the report stream.';
        setGenerationError(errorMsg);
        setStreamLog(prev => [...prev, `Stream connection failed. ${errorMsg}`]);
        setIsGenerating(false);
        es.close(); 
      };

    } catch (e: unknown) { 
        console.error("Failed to initialize EventSource:", e);
        // FIX: 'initErrorMsg' is never reassigned. Use 'const' instead.
        const initErrorMsg = "Failed to connect to the report generation service.";
        // if (e instanceof Error) { // This part was commented, making initErrorMsg effectively const
        //   // initErrorMsg = `Failed to connect: ${e.message}`;
        // }
        setGenerationError(initErrorMsg);
        setIsGenerating(false);
    }
  }, [currentProjectId]);

  const handleDownloadPdf = useCallback(async () => {
    if (!currentProjectId || !isPdfReady || isDownloadingPdf) return;

    setIsDownloadingPdf(true);
    setGenerationError(null); 

    try {
      const pdfApiUrl = `${API_BASE_URL}/api/agent3/report/pdf`;
      const formData = new FormData(); 
      formData.append('project_id', currentProjectId);

      const response = await fetch(pdfApiUrl, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        let errorDetail = `Server responded with ${response.status}.`;
        try {
            const errorJson = await response.json(); 
            errorDetail = errorJson.detail || errorDetail;
        // FIX: '_e' is defined but never used. Use empty catch parameters if error object isn't needed.
        } catch { /* Ignore if response is not JSON */ }
        throw new Error(`PDF download failed: ${errorDetail}`);
      }

      const blob = await response.blob();
      if (blob.type !== "application/pdf") {
        const errorText = await blob.text(); 
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

    } catch (err: unknown) { 
      console.error("PDF download error:", err);
      let messageToSet = 'An unknown error occurred during PDF download.';
      if (err instanceof Error) {
        messageToSet = err.message;
      } else if (typeof err === 'string') {
        messageToSet = err;
      }
      setGenerationError(messageToSet);
    } finally {
      setIsDownloadingPdf(false);
    }
  }, [currentProjectId, isPdfReady, isDownloadingPdf]);

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
          ) : preloadError && !markdownReport ? ( 
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

      {(isGenerating || streamLog.length > (markdownReport ? 0 : 1) ) && ( 
         <Card>
            <CardHeader><CardTitle className="text-lg">Generation Log</CardTitle></CardHeader>
            <CardContent>
                <pre className="text-xs bg-muted p-3 rounded-md max-h-60 overflow-y-auto whitespace-pre-wrap">
                    {streamLog.join('\n')}
                </pre>
            </CardContent>
         </Card>
      )}

      {markdownReport && !isGenerating && ( 
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
        // FIX: `"` can be escaped with `"` (Line 322 from error message)
        <p className="text-muted-foreground mt-4 text-center">No report generated yet for this project. Click "Generate Full Report" to start.</p>
      )}
    </div>
  );
}
