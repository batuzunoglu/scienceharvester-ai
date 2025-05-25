// frontend/src/context/ProjectsContext.tsx
'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';

// --- INTERFACES ---
export interface Paper {
  id: number | string;
  title: string;
  authors?: string[];
  publication_year?: number;
  doi?: string | null;
  journal_name?: string | null;
  abstract_snippet?: string | null;
  relevance_explanation_from_llm?: string | null;
  landing_page_url?: string;
  potential_oa_pdf_url?: string | null;
  suggested_filename?: string | null;
}

export interface TechFeature {
  feature_name: string;
  feature_value: string | number | string[] | number[];
  feature_unit: string | null;
  source_sentence: string;
}

export interface QualInsights {
  main_objective: string | null;
  key_materials_studied?: string[];
  key_methodology_summary?: string | null;
  primary_findings_conclusions?: string[];
  limitations_discussed_by_authors?: string[] | string | null;
  future_work_suggested_by_authors?: string[] | string | null;
  novelty_significance_claim?: string | null;
  key_tables_figures_present?: string | null;
}

export interface Extraction {
  filename: string;
  error?: string | null;
  technical_features: TechFeature[];
  qualitative_insights: QualInsights;
}

export interface Project {
  id: string;
  name: string;
  user_session_id?: string;
  data_dir?: string;
  agent1_metadata_file?: string | null;
  agent2_extraction_dir?: string;
  agent3_report_md_file?: string | null;
  agent3_report_pdf_file?: string | null;
  papers?: Paper[];
  extractions?: Extraction[];
}

interface ProjectsContextValue {
  projects: Project[];
  isLoading: boolean;
  fetchProjects(userSessionId?: string): Promise<void>;
  createProject(name: string, userSessionId: string): Promise<Project>;
  updatePapers(projectId: string, papers: Paper[]): void;
  updateExtractions(projectId: string, extractionsData: Extraction[]): void;
  getProject(id: string): Project | undefined;
  getProjectDetails(id: string): Promise<Project>;
}

// --- CONTEXT DEFINITION ---
const ProjectsContext = createContext<ProjectsContextValue | null>(null);
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// --- PROVIDER COMPONENT ---
export function ProjectsProvider({ children }: { children: React.ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [mounted, setMounted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const fetchProjects = useCallback(async (userSessionId?: string) => {
    setIsLoading(true);
    // console.log("Context: fetchProjects called with userSessionId:", userSessionId);
    try {
      let url = `${API_BASE_URL}/api/projects/`;
      if (userSessionId) {
        url += `?user_session_id=${encodeURIComponent(userSessionId)}`;
      }
      const response = await fetch(url);
      if (!response.ok) {
        const errorText = await response.text();
        console.error("Context: Failed to fetch projects from backend:", response.statusText, response.status, errorText);
        const localProjectsJson = localStorage.getItem('projects_cache');
        if (localProjectsJson) {
            try { setProjects(JSON.parse(localProjectsJson)); } catch { /* ignore */ }
        } else {
            setProjects([]);
        }
        return; 
      }
      const backendProjects: Project[] = await response.json();
      setProjects(backendProjects);
      localStorage.setItem('projects_cache', JSON.stringify(backendProjects));
    } catch (error) {
      console.error("Context: Error fetching projects:", error);
      const localProjectsJson = localStorage.getItem('projects_cache');
      if (localProjectsJson) {
        try { setProjects(JSON.parse(localProjectsJson)); } catch { /* ignore */ }
      } else {
        setProjects([]);
      }
    } finally {
        setIsLoading(false);
    }
  }, [setIsLoading]); // setIsLoading is stable

  const createProject = useCallback(async (name: string, userSessionId: string): Promise<Project> => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/projects/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, user_session_id: userSessionId }),
      });
      if (!response.ok) {
        const errorData = await response.text();
        throw new Error(`Failed to create project: ${response.status} - ${errorData.substring(0, 200)}`);
      }
      const newBackendProject: Project = await response.json();
      setProjects(ps => {
          const updatedProjects = [...ps, newBackendProject];
          localStorage.setItem('projects_cache', JSON.stringify(updatedProjects));
          return updatedProjects;
      });
      return newBackendProject;
    } catch (error) {
      console.error("Context: Error creating project:", error);
      throw error; 
    } finally {
        setIsLoading(false);
    }
  }, [setIsLoading]); // setIsLoading is stable

  const getProjectDetails = useCallback(async (id: string): Promise<Project> => {
    setIsLoading(true);
    try {
        const response = await fetch(`${API_BASE_URL}/api/projects/${id}`);
        if (!response.ok) {
            const errorText = await response.text();
            console.error(`Context: Failed to fetch project details for ${id}: ${response.status} ${errorText}`);
            throw new Error(`Failed to fetch project details for project ${id}. Status: ${response.status}. Details: ${errorText.substring(0,150)}`);
        }
        const projectDetail: Project = await response.json();
        setProjects(prevProjects => {
            const foundIndex = prevProjects.findIndex(p => p.id === id);
            const updatedProjects = [...prevProjects];
            if (foundIndex > -1) {
                updatedProjects[foundIndex] = { ...prevProjects[foundIndex], ...projectDetail };
            } else {
                updatedProjects.push(projectDetail);
            }
            localStorage.setItem('projects_cache', JSON.stringify(updatedProjects));
            return updatedProjects;
        });
        return projectDetail;
    } catch (error) {
        console.error(`Context: Error fetching project details for ${id}:`, error);
        throw error; 
    } finally {
        setIsLoading(false);
    }
  }, [setIsLoading]); // setIsLoading is stable

  const updatePapers = useCallback((projectId: string, papersData: Paper[]) => {
    setProjects(ps =>
      ps.map(p => (p.id === projectId ? { ...p, papers: papersData } : p))
    );
  }, []); // Stable

  const updateExtractions = useCallback((projectId: string, extractionsData: Extraction[]) => {
    setProjects(ps =>
      ps.map(p => (p.id === projectId ? { ...p, extractions: extractionsData } : p))
    );
  }, []); // Stable

  const getProject = useCallback((id: string): Project | undefined => {
    return projects.find(p => p.id === id);
  }, [projects]); // Stability tied to 'projects' state

  useEffect(() => {
    // Load projects from localStorage on initial mount
    const localProjectsJson = localStorage.getItem('projects_cache');
    if (localProjectsJson) {
        try {
            const cachedProjects = JSON.parse(localProjectsJson);
            if (Array.isArray(cachedProjects)) {
                setProjects(cachedProjects);
            }
        } catch {/*ignore parse error*/}
    }
    setMounted(true);
  }, []); // Runs once on mount

  if (!mounted) return null; 

  return (
    <ProjectsContext.Provider value={{
      projects,
      isLoading,
      fetchProjects,
      createProject,
      updatePapers,
      updateExtractions,
      getProject,
      getProjectDetails,
    }}>
      {children}
    </ProjectsContext.Provider>
  );
}

// --- HOOK TO USE CONTEXT ---
export const useProjects = () => {
  const ctx = useContext(ProjectsContext);
  if (!ctx) throw new Error("useProjects must be used within a ProjectsProvider");
  return ctx;
};