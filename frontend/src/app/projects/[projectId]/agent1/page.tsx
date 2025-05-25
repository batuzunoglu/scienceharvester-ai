// frontend/src/app/projects/[projectId]/agent1/page.tsx:
'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { useProjects } from '@/context/ProjectsContext';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/Spinner';
import { EventSourcePolyfill } from 'event-source-polyfill';

interface Paper {
    id: number; 
    title: string;
    authors: string[];
    publication_year: number;
    doi: string | null;
    journal_name: string | null;
    abstract_snippet: string | null;
    relevance_explanation_from_llm: string | null;
    landing_page_url: string;
    potential_oa_pdf_url: string | null;
    suggested_filename: string | null;
}

interface HarvestResult { 
    project_topic: string;
    date_filter_used: string;
    max_papers_requested: number;
    project_keywords: Record<string, string[]>; 
    papers: Paper[];
}

export default function Agent1Page() {
    const { projectId: rawProjectIdFromParams } = useParams();
    const { getProjectDetails } = useProjects(); 

    const [topic, setTopic] = useState('');
    const [dateAfter, setDateAfter] = useState('2020-01-01');
    const [dateBefore, setDateBefore] = useState(new Date().toISOString().slice(0, 10));
    const [maxPapers, setMaxPapers] = useState(5);

    const [isHarvesting, setIsHarvesting] = useState(false); 
    const [isPreloadingPageData, setIsPreloadingPageData] = useState(false);
    const [preloadError, setPreloadError] = useState<string | null>(null);

    const [logs, setLogs] = useState<string[]>([]);
    const [papers, setPapers] = useState<Paper[]>([]);
    const eventSourceRef = useRef<EventSourcePolyfill | null>(null);
    const resultReceivedSuccessfully = useRef(false); 
    
    const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
    const initialLoadAttemptedForId = useRef<string | null>(null);

    useEffect(() => {
        const projectIdString = Array.isArray(rawProjectIdFromParams) 
            ? rawProjectIdFromParams[0] 
            : rawProjectIdFromParams;
        
        if (projectIdString && projectIdString !== currentProjectId) {
            setCurrentProjectId(projectIdString);
            initialLoadAttemptedForId.current = null; 
            setLogs([]); 
            setPapers([]); 
            setTopic(''); 
        } else if (!projectIdString && currentProjectId !== null) {
            setCurrentProjectId(null); 
            initialLoadAttemptedForId.current = null;
        }
    }, [rawProjectIdFromParams, currentProjectId]);

    useEffect(() => {
        if (!currentProjectId || initialLoadAttemptedForId.current === currentProjectId) {
            return;
        }

        const loadProjectData = async () => {
            initialLoadAttemptedForId.current = currentProjectId; 
            setIsPreloadingPageData(true);
            setPreloadError(null);
            setPapers([]); 
            setLogs([`🔄 Initializing Agent 1 for project ID: ${currentProjectId}...`]); 

            try {
                const projectDetails = await getProjectDetails(currentProjectId); 
                setLogs(prev => [...prev, `✅ Project details loaded for "${projectDetails.name}"`]);
                setTopic(projectDetails.name || ''); 

                if (projectDetails.agent1_metadata_file) {
                    setLogs(prev => [...prev, `ℹ️ Previous Agent 1 data found. Fetching: ${projectDetails.agent1_metadata_file}`]);
                    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
                    const fileUrl = `${apiUrl}/api/projects/${currentProjectId}/files?file_key=agent1_metadata_file`;
                    
                    const response = await fetch(fileUrl);
                    if (!response.ok) {
                        const errorText = await response.text();
                        throw new Error(`Failed to fetch Agent 1 data file: ${response.status} ${errorText.substring(0, 200)}`);
                    }
                    const data: HarvestResult = await response.json();
                    
                    setLogs(prev => [...prev, `✅ Loaded ${data.papers?.length || 0} papers from previous run.`]);
                    setPapers(data.papers || []);
                    setTopic(data.project_topic || projectDetails.name || ''); 
                    if (data.date_filter_used) {
                        const dates = data.date_filter_used.split(' to ');
                        if (dates.length === 2) { setDateAfter(dates[0]); setDateBefore(dates[1]); }
                    }
                    if (data.max_papers_requested) { setMaxPapers(data.max_papers_requested); }
                    setLogs(prev => [...prev, "💡 Displaying preloaded data. Modify and start a new harvest or review."]);
                } else {
                    setLogs(prev => [...prev, "ℹ️ No previous Agent 1 data found. Form is ready for a new harvest."]);
                }
            } catch (error: any) {
                const errorMessage = error.message || "An unknown error occurred during preloading.";
                setLogs(prev => [...prev, `❌ Error preloading Agent 1 data: ${errorMessage}`]);
                setPreloadError(errorMessage);
                setTopic(''); 
            } finally {
                setIsPreloadingPageData(false);
            }
        };

        if (currentProjectId) loadProjectData();
        return () => {
            if (eventSourceRef.current) eventSourceRef.current.close();
        };
    }, [currentProjectId, getProjectDetails]); 

    const handleSubmitHarvest = (e: React.FormEvent) => {
        e.preventDefault();
        if (!currentProjectId) {
            setLogs(prev => [...prev, "❌ Error: Project ID is missing. Cannot start harvest."]);
            return; 
        }

        resultReceivedSuccessfully.current = false; 
        setIsHarvesting(true); // Set loading state first
        setPapers([]); // Clear previous papers
        setLogs(["🚀 Initializing new harvest request..."]); 

        if (eventSourceRef.current) eventSourceRef.current.close();

        const params = new URLSearchParams({
            topic, dateAfter, dateBefore,
            maxPapers: String(maxPapers),
            project_id: currentProjectId, 
        });

        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const url = `${apiUrl}/api/agent1/harvest/stream?${params.toString()}`;
        setLogs(prev => [...prev, `🔌 Connecting to stream: ${url}`]);

        const es = new EventSourcePolyfill(url, { heartbeatTimeout: 200_000 });
        eventSourceRef.current = es;

        es.onopen = () => {
            setLogs(l => [...l, "SSE Connection established."]);
        };

        es.onmessage = (evt) => {
          const data = evt.data;
          // console.log("[SSE ONMESSAGE] Received raw data:", JSON.stringify(data)); // Keep this for debugging if you want

          // MODIFIED LINE 1: Check for double underscore
          if (data.startsWith('__RESULT__')) { 
              // console.log("[SSE ONMESSAGE] Matched: data.startsWith('__RESULT__')"); // Optional debug log
              resultReceivedSuccessfully.current = true; 
              setLogs(l => [...l, "✅ Received final result."]); 
              
              let parsedPapers: Paper[] = [];
              try {
                  // MODIFIED LINE 2: Replace double underscore
                  const payloadString = data.replace('__RESULT__', ''); 
                  // console.log("[SSE ONMESSAGE] Payload string for __RESULT__ (first 100 chars):", payloadString.substring(0,100) + "..."); 
                  const payload: HarvestResult = JSON.parse(payloadString);
                  parsedPapers = payload.papers || [];
                  // console.log("[SSE ONMESSAGE] Parsed payload, setPapers with:", parsedPapers.length > 0 ? parsedPapers[0].title : "No papers");
                  setPapers(parsedPapers); 
                  // console.log("[SSE ONMESSAGE] Called setPapers.");
              } catch (parseError: any) {
                  console.error("Agent1Page: Failed to parse result payload:", parseError, "Data:", data);
                  setLogs(l => [...l, `❌ Error parsing final result: ${parseError.message}`]);
                  setPapers([]); 
                  // console.log("[SSE ONMESSAGE] Parse error, called setPapers([]).");
              }
              
              setIsHarvesting(false); 
              // console.log("[SSE ONMESSAGE] Called setIsHarvesting(false).");

              if (eventSourceRef.current) {
                  // console.log("[SSE ONMESSAGE] Closing EventSource after __RESULT__ processing.");
                  eventSourceRef.current.close();
              }
              // console.log("[SSE ONMESSAGE] Returning after __RESULT__ processing.");
              return; 
          } 
          
          // The ERROR check should be fine if your server sends "ERROR" consistently
          if (data.startsWith('ERROR')) { 
              // console.log("[SSE ONMESSAGE] Matched: data.startsWith('ERROR')");
              setLogs(l => [...l, `❌ Server Error: ${data.replace('ERROR', '')}`]);
              setIsHarvesting(false);
              setPapers([]); 
              if (eventSourceRef.current) {
                  // console.log("[SSE ONMESSAGE] Closing EventSource after ERROR processing.");
                  eventSourceRef.current.close();
              }
              // console.log("[SSE ONMESSAGE] Returning after ERROR processing.");
              return; 
          } 
          
          // If it reaches here, it's neither __RESULT__ nor ERROR
          // This is where the "flusso: __RESULT__" was wrongly appearing because the above 'if' failed
          // console.log("[SSE ONMESSAGE] Did not match __RESULT__ or ERROR. Logging as 'flusso'. Raw Data:", JSON.stringify(data));
          setLogs(l => [...l, ` flusso: ${data}`]);
      };

      es.onerror = (err) => {
        console.log("[SSE ONERROR] onerror triggered. Result received flag:", resultReceivedSuccessfully.current, "Current isHarvesting state:", isHarvesting);
        
        if (resultReceivedSuccessfully.current) {
            // If result was already received, this "error" is likely the stream closing normally.
            if (isHarvesting) { // Should ideally be false already if onmessage for RESULT ran
                console.log("[SSE ONERROR] Result was received, but isHarvesting is still true. Defensively setting to false.");
                setIsHarvesting(false); 
            }
            if (eventSourceRef.current && eventSourceRef.current.readyState !== EventSource.CLOSED) {
                console.log("[SSE ONERROR] Result was received. Closing EventSource from onerror if not already closed.");
                eventSourceRef.current.close();
            }
            console.log("[SSE ONERROR] Result was received. Ignoring error for UI error message purposes, stream likely closed by server.");
            return; 
        }
        
        // This is a genuine error before a successful result was flagged
        console.error("Agent1Page: EventSource failed (genuine error before result):", err);
        setLogs(l => [...l, "❌ Connection error with the stream. Check server logs."]);
        
        if (papers.length > 0) { // If there were papers from a previous successful load, clear them on new error
            console.log("[SSE ONERROR] Genuine error, clearing existing papers.");
            setPapers([]); 
        }
        
        if (isHarvesting) { // Only set if it was true, to avoid unnecessary re-renders if already false
             setIsHarvesting(false); 
             console.log("[SSE ONERROR] Genuine error, called setIsHarvesting(false).");
        }

        if (eventSourceRef.current) {
            console.log("[SSE ONERROR] Closing EventSource due to genuine error.");
            eventSourceRef.current.close();
        }
    };
    };

    const disableForm = isHarvesting || isPreloadingPageData || !currentProjectId;

    return (
        <div className="p-6 max-w-4xl mx-auto space-y-6">
            <h1 className="text-2xl font-semibold">Agent 1: Harvest Papers</h1>

            {isPreloadingPageData && (
                <div className="flex items-center space-x-2 text-gray-500 p-2 bg-gray-100 dark:bg-gray-700 dark:text-gray-300 rounded">
                    <Spinner size={16} /> <span>Loading existing project data...</span>
                </div>
            )}
            {preloadError && !isPreloadingPageData && (
                 <p className="text-red-600 dark:text-red-400 p-2 bg-red-100 dark:bg-red-900 dark:border dark:border-red-700 rounded">
                    Preload Error: {preloadError}
                 </p>
            )}
            {!currentProjectId && !isPreloadingPageData && !isHarvesting && (
                <p className="text-orange-500">Waiting for project selection or initializing...</p>
            )}

            <form onSubmit={handleSubmitHarvest} className="space-y-4">
                <div>
                    <Label htmlFor="topic-input">Research Topic</Label>
                    <Input id="topic-input" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Enter research topic" required disabled={disableForm} />
                </div>
                <div className="flex space-x-4">
                    <div className="flex-1">
                        <Label htmlFor="dateAfter-input">Date After</Label>
                        <Input id="dateAfter-input" type="date" value={dateAfter} onChange={(e) => setDateAfter(e.target.value)} disabled={disableForm} />
                    </div>
                    <div className="flex-1">
                        <Label htmlFor="dateBefore-input">Date Before</Label>
                        <Input id="dateBefore-input" type="date" value={dateBefore} onChange={(e) => setDateBefore(e.target.value)} disabled={disableForm} />
                    </div>
                </div>
                <div>
                    <Label htmlFor="maxPapers-input">Max Papers (1–15)</Label>
                    <Input id="maxPapers-input" type="number" min={1} max={15} value={maxPapers} onChange={(e) => setMaxPapers(Number(e.target.value))} disabled={disableForm} />
                </div>
                <Button type="submit" disabled={disableForm || !topic.trim()}>
                    {isHarvesting ? <Spinner size={16} /> : (isPreloadingPageData ? 'Loading...' : 'Harvest Papers')}
                </Button>
            </form>

            {(logs.length > 0) && (
                <Card className="mt-4">
                    <CardContent className="p-4">
                        <h3 className="text-lg font-medium mb-2">Activity Log</h3>
                        <div className="bg-gray-50 dark:bg-gray-800 p-3 rounded-md max-h-60 overflow-y-auto space-y-1">
                            {logs.map((line, i) => <pre key={i} className="text-sm font-mono whitespace-pre-wrap break-all">{line}</pre>)}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Display papers: ensure !isHarvesting is true AND papers have content */}
            {!isHarvesting && papers.length > 0 && (
                <div className="space-y-4 mt-6">
                    <h2 className="text-xl font-semibold">
                        {/* Title differentiation based on logs, check if a harvest was just run or if it's preloaded */}
                        {logs.some(log => log.includes("Initializing new harvest request...")) || !logs.some(log => log.includes("Displaying preloaded data"))
                            ? "Harvested Papers" 
                            : "Previously Harvested Papers"} 
                        ({papers.length})
                    </h2>
                    {papers.map((p) => (
                        <Card key={p.id || p.doi}> 
                            <CardContent className="p-4">
                                <h3 className="text-lg font-semibold mb-1">{p.title}</h3>
                                <p className="text-sm text-gray-600 dark:text-gray-400"><strong>Authors:</strong> {p.authors?.join(', ') || 'N/A'}</p>
                                <p className="text-sm text-gray-600 dark:text-gray-400"><strong>Year:</strong> {p.publication_year || 'N/A'} | <strong>Journal:</strong> {p.journal_name || 'N/A'}</p>
                                {p.doi && <p className="text-sm text-gray-600 dark:text-gray-400"><strong>DOI:</strong> {p.doi}</p>}
                                {p.abstract_snippet && <p className="text-sm italic my-2 p-2 bg-gray-50 dark:bg-gray-700 rounded">“{p.abstract_snippet}”</p>}
                                {p.relevance_explanation_from_llm && <p className="text-sm my-2"><strong>Relevance:</strong> {p.relevance_explanation_from_llm}</p>}
                                {p.landing_page_url && <a href={p.landing_page_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-blue-400 hover:underline text-sm">View Paper Details</a>}
                                {p.potential_oa_pdf_url && <a href={p.potential_oa_pdf_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-blue-400 hover:underline text-sm ml-2">(Potential PDF)</a>}
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Message for "No papers to display" */}
            {!isHarvesting && !isPreloadingPageData && papers.length === 0 && 
             currentProjectId && 
             (logs.some(log => log.includes("Received final result.")) || // Specifically check if a harvest attempt that *should* have results finished
                logs.some(log => log.includes("No previous Agent 1 data found")) ||
                logs.some(log => log.includes("Error preloading Agent 1 data")) ||
                logs.some(log => log.includes("Server Error")) ||
                logs.some(log => log.includes("Connection error with the stream")) 
             ) && (
                 <p className="mt-4 text-gray-700 dark:text-gray-300">No papers found or an error occurred. Check logs for details.</p>
            )}
        </div>
    );
}