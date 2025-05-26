// frontend/src/context/ProjectsContext.tsx
'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';

// --- INTERFACES (assuming these are correct and unchanged) ---
export interface Paper { id: number | string; title: string; authors?: string[]; publication_year?: number; doi?: string | null; journal_name?: string | null; abstract_snippet?: string | null; relevance_explanation_from_llm?: string | null; landing_page_url?: string; potential_oa_pdf_url?: string | null; suggested_filename?: string | null; }
export interface TechFeature { feature_name: string; feature_value: string | number | string[] | number[]; feature_unit: string | null; source_sentence: string; }
export interface QualInsights { main_objective: string | null; key_materials_studied?: string[]; key_methodology_summary?: string | null; primary_findings_conclusions?: string[]; limitations_discussed_by_authors?: string[] | string | null; future_work_suggested_by_authors?: string[] | string | null; novelty_significance_claim?: string | null; key_tables_figures_present?: string | null; }
export interface Extraction { filename: string; error?: string | null; technical_features: TechFeature[]; qualitative_insights: QualInsights; }
export interface Project { id: string; name: string; user_session_id?: string; data_dir?: string; agent1_metadata_file?: string | null; agent2_extraction_dir?: string; agent3_report_md_file?: string | null; agent3_report_pdf_file?: string | null; papers?: Paper[]; extractions?: Extraction[]; created_at?: string; updated_at?: string; }
interface ProjectsContextValue { projects: Project[]; isLoading: boolean; fetchProjects(userSessionId?: string): Promise<void>; createProject(name: string, userSessionId: string): Promise<Project>; updatePapers(projectId: string, papers: Paper[]): void; updateExtractions(projectId: string, extractionsData: Extraction[]): void; getProject(id: string): Project | undefined; getProjectDetails(id: string): Promise<Project>; }

const ProjectsContext = createContext<ProjectsContextValue | null>(null);
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

export function ProjectsProvider({ children }: { children: React.ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [mounted, setMounted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const fetchProjects = useCallback(async (userSessionId?: string) => {
    setIsLoading(true);
    console.log("Context: fetchProjects called with userSessionId:", userSessionId);
    try {
      // === Path Change: No trailing slash after "projects" ===
      let url = `${API_BASE_URL}/api/projects`;
      // =======================================================
      if (userSessionId) {
        url += `?user_session_id=${encodeURIComponent(userSessionId)}`;
      }
      console.log("Context: Fetching projects from URL:", url);

      const response = await fetch(url);
      if (!response.ok) {
        const errorText = await response.text();
        const errorMessage = `Context: Failed to fetch projects from backend: ${response.status} ${response.statusText}. Details: ${errorText.substring(0, 200)}`;
        console.error(errorMessage);
        const localProjectsJson = localStorage.getItem('projects_cache');
        if (localProjectsJson) { try { setProjects(JSON.parse(localProjectsJson)); } catch { /* ignore */ } }
        else { setProjects([]); }
        throw new Error(errorMessage);
      }
      const backendProjects: Project[] = await response.json();
      setProjects(backendProjects);
      localStorage.setItem('projects_cache', JSON.stringify(backendProjects));
    } catch (error) {
      console.error("Context: Error during fetchProjects:", error);
      const localProjectsJson = localStorage.getItem('projects_cache');
      if (localProjectsJson) { try { setProjects(JSON.parse(localProjectsJson)); } catch { /* ignore */ } }
      else { setProjects([]); }
      throw error;
    } finally {
        setIsLoading(false);
    }
  }, [setIsLoading]);

  const createProject = useCallback(async (name: string, userSessionId: string): Promise<Project> => {
    setIsLoading(true);
    console.log("Context: createProject called with name:", name, "userSessionId:", userSessionId);
    try {
      // === Path Change: No trailing slash after "projects" ===
      const response = await fetch(`${API_BASE_URL}/api/projects`, {
      // =======================================================
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, user_session_id: userSessionId }),
      });
      console.log("Context: createProject response status:", response.status);
      if (!response.ok) {
        const errorData = await response.text();
        const errorMessage = `Failed to create project: ${response.status} - ${errorData.substring(0, 200)}`;
        console.error("Context: createProject error:", errorMessage);
        throw new Error(errorMessage);
      }
      const newBackendProject: Project = await response.json();
      console.log("Context: Project created successfully:", newBackendProject.id);
      setProjects(ps => {
          const updatedProjects = [...ps, newBackendProject];
          localStorage.setItem('projects_cache', JSON.stringify(updatedProjects));
          return updatedProjects;
      });
      return newBackendProject;
    } catch (error) {
      console.error("Context: Error during createProject:", error);
      throw error; 
    } finally {
        setIsLoading(false);
    }
  }, [setIsLoading]);

  const getProjectDetails = useCallback(async (id: string): Promise<Project> => {
    setIsLoading(true);
    console.log("Context: getProjectDetails called for ID:", id);
    try {
      // === Path Change: No trailing slash after "projects" ===
      // This path will be /api/projects/{id}
      const response = await fetch(`${API_BASE_URL}/api/projects/${id}`);
      // =======================================================
      console.log("Context: getProjectDetails response status:", response.status);
      if (!response.ok) {
            const errorText = await response.text();
            const errorMessage = `Context: Failed to fetch project details for ${id}: ${response.status} ${errorText.substring(0,150)}`;
            console.error(errorMessage);
            throw new Error(errorMessage);
        }
        const projectDetail: Project = await response.json();
        console.log("Context: Project details fetched for:", projectDetail.id);
        setProjects(prevProjects => {
            const foundIndex = prevProjects.findIndex(p => p.id === id);
            const updatedProjects = [...prevProjects];
            if (foundIndex > -1) { updatedProjects[foundIndex] = { ...prevProjects[foundIndex], ...projectDetail }; }
            else { updatedProjects.push(projectDetail); }
            localStorage.setItem('projects_cache', JSON.stringify(updatedProjects));
            return updatedProjects;
        });
        return projectDetail;
    } catch (error) {
        console.error(`Context: Error during getProjectDetails for ${id}:`, error);
        throw error; 
    } finally {
        setIsLoading(false);
    }
  }, [setIsLoading]);

  const updatePapers = useCallback((projectId: string, papersData: Paper[]) => {
    console.log("Context: updatePapers called for projectId:", projectId);
    setProjects(ps => {
      const updated = ps.map(p => (p.id === projectId ? { ...p, papers: papersData } : p));
      localStorage.setItem('projects_cache', JSON.stringify(updated));
      return updated;
    });
  }, []);

  const updateExtractions = useCallback((projectId: string, extractionsData: Extraction[]) => {
    console.log("Context: updateExtractions called for projectId:", projectId);
    setProjects(ps => {
      const updated = ps.map(p => (p.id === projectId ? { ...p, extractions: extractionsData } : p));
      localStorage.setItem('projects_cache', JSON.stringify(updated));
      return updated;
    });
  }, []);

  const getProject = useCallback((id: string): Project | undefined => {
    return projects.find(p => p.id === id);
  }, [projects]);

  useEffect(() => {
    console.log("Context: Initial mount effect running to load from localStorage.");
    const localProjectsJson = localStorage.getItem('projects_cache');
    if (localProjectsJson) {
        try {
            const cachedProjects = JSON.parse(localProjectsJson);
            if (Array.isArray(cachedProjects)) {
                setProjects(cachedProjects);
                console.log("Context: Loaded", cachedProjects.length, "projects from localStorage.");
            } else { console.log("Context: Data from localStorage is not an array.");}
        } catch (e) { console.error("Context: Error parsing projects from localStorage:", e); }
    } else { console.log("Context: No projects_cache found in localStorage."); }
    setMounted(true);
  }, []);

  if (!mounted) { return null; }

  return (
    <ProjectsContext.Provider value={{ projects, isLoading, fetchProjects, createProject, updatePapers, updateExtractions, getProject, getProjectDetails, }}>
      {children}
    </ProjectsContext.Provider>
  );
}

export const useProjects = () => {
  const ctx = useContext(ProjectsContext);
  if (!ctx) { throw new Error("useProjects must be used within a ProjectsProvider."); }
  return ctx;
};
