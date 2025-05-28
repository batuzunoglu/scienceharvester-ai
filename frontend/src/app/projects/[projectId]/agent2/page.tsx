// /Users/batu/Desktop/Projects/scienceharvester-ai/frontend/src/app/projects/[projectId]/agent2/page.tsx:
'use client';

import React, { useState, useEffect, useCallback } from 'react'; // Added useEffect, useCallback
import { useParams } from 'next/navigation';
import { useProjects, Project, Extraction, QualInsights } from '@/context/ProjectsContext'; // Assuming Extraction, TechFeature, QualInsights are exported from context
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/Spinner';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function Agent2Page() {
  const { projectId: rawProjectId } = useParams();
  const { getProjectDetails, updateExtractions } = useProjects(); // Added getProjectDetails

  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
  const [project, setProject] = useState<Project | null | undefined>(null);

  const [files, setFiles] = useState<FileList | null>(null);
  const [isExtracting, setIsExtracting] = useState(false); // For active extraction
  
  // State for displayed results (can be combination of preloaded and newly extracted)
  const [extractionResults, setExtractionResults] = useState<Extraction[]>([]);

  // Preloading state
  const [isPreloading, setIsPreloading] = useState(true);
  const [preloadError, setPreloadError] = useState<string | null>(null);
  
  const [extractionError, setExtractionError] = useState<string | null>(null);


  // Stabilize projectId
  useEffect(() => {
    const pid = Array.isArray(rawProjectId) ? rawProjectId[0] : rawProjectId;
    if (pid) {
      setCurrentProjectId(pid);
    }
  }, [rawProjectId]);

  // Fetch project details and then preload extractions
  const loadInitialData = useCallback(async () => {
    if (!currentProjectId) {
      setIsPreloading(false);
      return;
    }

    setIsPreloading(true);
    setPreloadError(null);
    setExtractionResults([]); // Clear existing before loading

    try {
      const details = await getProjectDetails(currentProjectId);
      setProject(details); // Store full project details if needed by UI

      // Fetch list of existing extraction files
      const listRes = await fetch(`${API_BASE_URL}/api/projects/${currentProjectId}/agent2_extractions`);
      if (!listRes.ok) {
        const errorText = await listRes.text();
        throw new Error(`Failed to list Agent 2 extractions: ${listRes.status} ${errorText.substring(0,100)}`);
      }
      const { files: extractionFilenames } = await listRes.json() as { files: string[] };

      if (extractionFilenames && extractionFilenames.length > 0) {
        const preloaded: Extraction[] = [];
        // Fetch content for each file - consider doing this in parallel for many files
        for (const filename of extractionFilenames) {
          try {
            const fileRes = await fetch(`${API_BASE_URL}/api/projects/${currentProjectId}/agent2_extractions/${filename}`);
            if (!fileRes.ok) {
              console.warn(`Failed to fetch Agent 2 extraction content for ${filename}: ${fileRes.status}`);
              // Optionally add a placeholder or error entry for this file
              preloaded.push({
                filename: filename,
                error: `Failed to load pre-existing data (status: ${fileRes.status})`,
                technical_features: [],
                qualitative_insights: { main_objective: null } as QualInsights // Provide minimal valid structure
              });
              continue;
            }
            const extractionContent: Extraction = await fileRes.json();
            preloaded.push(extractionContent);
          } catch (fileError: unknown) {
             console.warn(`Error fetching or parsing content for ${filename}: ${(fileError as Error).message}`);
             preloaded.push({
                filename: filename,
                error: `Error loading pre-existing data: ${fileError.message.substring(0,100)}`,
                technical_features: [],
                qualitative_insights: { main_objective: null } as QualInsights
              });
          }
        }
        setExtractionResults(preloaded);
        updateExtractions(currentProjectId, preloaded); // Update context if you want
        console.log(`Agent2Page: Preloaded ${preloaded.length} extractions for project ${currentProjectId}`);
      } else {
        console.log(`Agent2Page: No pre-existing Agent 2 extractions found for project ${currentProjectId}`);
      }
    } catch (err: unknown) {
      console.error("Agent2Page: Error during preloading:", err);
      setPreloadError((err as Error).message || 'Failed to load initial project data.');
    } finally {
      setIsPreloading(false);
    }
  }, [currentProjectId, getProjectDetails, updateExtractions]); // API_BASE_URL is stable

  useEffect(() => {
    if (currentProjectId) {
      // console.log("Agent2Page: Current Project ID set, attempting to load initial data:", currentProjectId);
      loadInitialData();
    } else {
      // console.log("Agent2Page: Current Project ID is null, skipping initial data load.");
      setProject(undefined); // Clear project if no ID
      setExtractionResults([]); // Clear results
      setIsPreloading(false); // Not preloading if no project ID
    }
  }, [currentProjectId, loadInitialData]);


  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!files || files.length === 0 || !currentProjectId) {
        setExtractionError("Please select PDF files and ensure a project is active.");
        return;
    }

    setIsExtracting(true);
    setExtractionError(null);
    // Decide: clear old results, or append? For now, let's clear for simplicity.
    // If you want to append, you'd merge with `extractionResults`
    // setExtractionResults([]); 

    try {
      const form = new FormData();
      Array.from(files).forEach((f) => form.append('pdfs', f));
      form.append('project_id', currentProjectId); // Use project_id as expected by backend

      const res = await fetch(`${API_BASE_URL}/api/agent2/extract`, {
        method: 'POST',
        body: form,
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: `Server responded ${res.status}` }));
        throw new Error(errorData.detail || `Server responded ${res.status}`);
      }
      const jsonResponse = await res.json();
      
      if (jsonResponse.extractions && Array.isArray(jsonResponse.extractions)) {
        // New extractions will replace preloaded ones for now
        setExtractionResults(jsonResponse.extractions);
        updateExtractions(currentProjectId, jsonResponse.extractions); // Update context
      } else {
        throw new Error("Received invalid extraction data from server.");
      }

    } catch (err: unknown) {
      console.error("Agent2Page: Extraction error:", err);
      setExtractionError((err as Error).message || 'Unknown error during extraction.');
    } finally {
      setIsExtracting(false);
    }
  }
  
  // Display logic
  let resultsContent;
  if (isPreloading) {
    resultsContent = (
      <div className="flex items-center space-x-2 text-gray-500 mt-4">
        <Spinner size={20} /> <span>Loading previous extractions...</span>
      </div>
    );
  } else if (preloadError) {
    resultsContent = <p className="text-red-500 mt-4">Error loading previous data: {preloadError}</p>;
  } else if (extractionResults.length > 0) {
    resultsContent = extractionResults.map((ext, index) => (
      <Card key={ext.filename + index} className="mt-4"> {/* Ensure key is unique */}
        <CardContent className="p-4 space-y-3">
          <h2 className="text-xl font-semibold">{ext.filename}</h2>
          {ext.error && <p className="text-red-500">Error processing this PDF: {ext.error}</p>}
          
          {!ext.error && (
            <>
              <div>
                <h3 className="text-lg font-medium mb-1">Technical Features</h3>
                {ext.technical_features?.length > 0 ? (
                  ext.technical_features.map((f, i) => (
                    <div key={`tech-${i}`} className="pl-2 border-l-2 border-gray-200 dark:border-gray-700 mb-2 pb-1">
                      <p>
                        <strong>{f.feature_name}</strong>:{' '}
                        {Array.isArray(f.feature_value)
                          ? f.feature_value.join(', ')
                          : f.feature_value}{' '}
                        {f.feature_unit || ''}
                      </p>
                      <p className="italic text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                        Source: “{f.source_sentence}”
                      </p>
                    </div>
                  ))
                ) : <p className="text-sm text-gray-500">No technical features extracted.</p>}
              </div>

              <div>
                <h3 className="text-lg font-medium mb-1">Qualitative Insights</h3>
                {ext.qualitative_insights && Object.keys(ext.qualitative_insights).length > 0 && ext.qualitative_insights.main_objective ? (
                  <div className="pl-2 border-l-2 border-gray-200 dark:border-gray-700 space-y-1 text-sm">
                    <p><strong>Objective:</strong> {ext.qualitative_insights.main_objective || 'N/A'}</p>
                    <p><strong>Materials:</strong> {ext.qualitative_insights.key_materials_studied?.join(', ') || 'N/A'}</p>
                    <p><strong>Method:</strong> {ext.qualitative_insights.key_methodology_summary || 'N/A'}</p>
                    <p><strong>Findings:</strong> {ext.qualitative_insights.primary_findings_conclusions?.join('; ') || 'N/A'}</p>
                    {ext.qualitative_insights.limitations_discussed_by_authors && <p><strong>Limitations:</strong> {Array.isArray(ext.qualitative_insights.limitations_discussed_by_authors) ? ext.qualitative_insights.limitations_discussed_by_authors.join('; ') : ext.qualitative_insights.limitations_discussed_by_authors}</p>}
                    {ext.qualitative_insights.future_work_suggested_by_authors && <p><strong>Future Work:</strong> {Array.isArray(ext.qualitative_insights.future_work_suggested_by_authors) ? ext.qualitative_insights.future_work_suggested_by_authors.join('; ') : ext.qualitative_insights.future_work_suggested_by_authors}</p>}
                    {ext.qualitative_insights.novelty_significance_claim && <p><strong>Novelty:</strong> {ext.qualitative_insights.novelty_significance_claim}</p>}
                    {ext.qualitative_insights.key_tables_figures_present && <p><strong>Tables/Figures:</strong> {ext.qualitative_insights.key_tables_figures_present}</p>}
                  </div>
                ) : <p className="text-sm text-gray-500">No qualitative insights extracted.</p>}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    ));
  } else if (!isExtracting) { // Show only if not currently extracting and no preloaded/error
    resultsContent = <p className="text-gray-500 mt-4">No extractions to display. Upload PDFs to begin.</p>;
  }


  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold">Agent 2: Extract Features from PDFs</h1>
      <p className="text-sm text-gray-600">
        Project: {project?.name || currentProjectId || 'Loading project...'}
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <Label htmlFor="pdf-upload">Upload PDF(s) for Extraction</Label>
          <Input
            id="pdf-upload"
            type="file"
            accept=".pdf"
            multiple
            onChange={(e) => setFiles(e.target.files)}
            disabled={isExtracting || isPreloading}
          />
        </div>
        <Button type="submit" disabled={isExtracting || isPreloading || !files || files.length === 0}>
          {isExtracting ? <Spinner size={16} /> : 'Start Extraction'}
        </Button>
      </form>

      {extractionError && <p className="text-red-500 mt-2">Extraction Error: {extractionError}</p>}

      {isExtracting && (
        <div className="flex items-center space-x-2 mt-4">
          <Spinner size={24} />
          <span>Extracting features from PDFs, please wait... This may take a while.</span>
        </div>
      )}
      
      <div className="mt-6 space-y-4">
        {resultsContent}
      </div>
    </div>
  );
}
