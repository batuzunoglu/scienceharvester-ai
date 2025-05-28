'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useProjects } from '@/context/ProjectsContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import Link from 'next/link';
import { Spinner } from '@/components/Spinner';
import {
    Card,
    CardHeader,
    CardTitle,
    CardContent,
    CardFooter,
    CardDescription,
} from '@/components/ui/card';
import {
    PlusCircle,
    AlertTriangle,
    FolderKanban,
    ArrowRight,
    Loader2,
    ServerCrash,
    Inbox,
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export default function ProjectsPage() {
    const { projects, createProject, fetchProjects, isLoading: isContextLoading } = useProjects();
    const [newProjectName, setNewProjectName] = useState('');
    const router = useRouter();

    const [pageLoadingState, setPageLoadingState] = useState<'idle' | 'session_init' | 'loading_projects' | 'projects_loaded' | 'error'>('session_init');
    const [isCreatingProject, setIsCreatingProject] = useState(false);
    const [userSessionId, setUserSessionId] = useState<string | null>(null);
    const [pageError, setPageError] = useState<string | null>(null);

    const projectsFetchedForCurrentSession = useRef<string | null>(null);

    // Effect 1: Establish userSessionId
    useEffect(() => {
        let sessionIdFromStorage = localStorage.getItem('user_session_id');
        if (!sessionIdFromStorage) {
            sessionIdFromStorage = Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
            localStorage.setItem('user_session_id', sessionIdFromStorage);
        }
        if (userSessionId !== sessionIdFromStorage) {
            setUserSessionId(sessionIdFromStorage);
        }
    }, [userSessionId]);

    // Effect 2: Load projects
    useEffect(() => {
        if (userSessionId && projectsFetchedForCurrentSession.current !== userSessionId) {
            const loadProjects = async (sid: string) => {
                setPageLoadingState('loading_projects');
                setPageError(null);
                try {
                    await fetchProjects(sid);
                    projectsFetchedForCurrentSession.current = sid;
                    setPageLoadingState('projects_loaded');
                } catch (err: any) {
                    console.error("ProjectsPage: Failed to load projects:", err);
                    setPageError(err.message || "Could not load projects. Please try again later.");
                    setPageLoadingState('error');
                }
            };
            loadProjects(userSessionId);
        } else if (userSessionId && projectsFetchedForCurrentSession.current === userSessionId && pageLoadingState !== 'projects_loaded') {
            setPageLoadingState('projects_loaded');
        }
    }, [userSessionId, fetchProjects, pageLoadingState]);

    // --- Handlers ---
    const handleCreateNewProject = async (e: React.FormEvent) => {
        e.preventDefault();
        setPageError(null);
        const trimmedName = newProjectName.trim();
        if (!trimmedName || !userSessionId) {
            setPageError(!trimmedName ? "Project name cannot be empty." : "User session not available. Please refresh.");
            return;
        }
        setIsCreatingProject(true);
        try {
            const newProject = await createProject(trimmedName, userSessionId);
            if (newProject && newProject.id) {
                setNewProjectName('');
                router.push(`/projects/${newProject.id}/agent1`);
            } else {
                throw new Error("Project creation returned invalid data.");
            }
        } catch (err: any) {
            console.error("Error creating project:", err);
            setPageError(err.message || "Failed to create project.");
        } finally {
            setIsCreatingProject(false);
        }
    };

    // --- Derived State ---
    const isInputDisabled = isCreatingProject || isContextLoading || pageLoadingState !== 'projects_loaded';
    const isButtonDisabled = isInputDisabled || !newProjectName.trim() || !userSessionId;

    // --- Render Logic ---
    const renderLoadingState = () => (
        <div className="flex flex-col items-center justify-center text-center py-24 bg-white rounded-xl shadow-sm border border-gray-100">
            <Loader2 className="h-16 w-16 text-blue-500 animate-spin" />
            <p className="mt-6 text-xl font-medium text-gray-700">
                {pageLoadingState === 'session_init' ? 'Initializing Session...' : 'Loading Your Projects...'}
            </p>
            <p className="mt-2 text-base text-gray-500">Hang tight, we are getting things ready for you.</p>
        </div>
    );

    const renderErrorState = () => (
        <Alert variant="destructive" className="py-8 text-center bg-red-50 border-red-200">
            <ServerCrash className="h-12 w-12 mx-auto text-red-500" />
            <AlertTitle className="text-xl font-bold mt-4">Load Error!</AlertTitle>
            <AlertDescription className="text-base mt-2">
                {pageError || "We couldn&apos;t load your projects. Please check your connection and try again."}
            </AlertDescription>
            <Button
                variant="destructive"
                className="mt-6"
                onClick={() => userSessionId && fetchProjects(userSessionId)}
                disabled={isContextLoading}
            >
                {isContextLoading ? <Spinner size={16} /> : 'Retry Loading'}
            </Button>
        </Alert>
    );

    const renderEmptyState = () => (
         <div className="text-center py-24 border-2 border-dashed border-gray-300 rounded-xl bg-gray-50">
            <Inbox className="mx-auto h-16 w-16 text-gray-400" />
            <h3 className="mt-4 text-xl font-semibold text-gray-900">Your workspace is empty!</h3>
            <p className="mt-2 text-base text-gray-500">Looks like you have not created any projects yet.</p>
             <p className="mt-1 text-base text-gray-500">Use the form above to start your first project.</p>
        </div>
    );

    const renderProjectsList = () => (
        <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map(p => (
                <li key={p.id}>
                    <Link href={`/projects/${p.id}/agent1`} passHref className="group block h-full">
                        <Card className="hover:shadow-xl hover:border-blue-500 transition-all duration-300 ease-in-out cursor-pointer h-full flex flex-col border border-gray-200 bg-white">
                            <CardHeader className="flex-row items-start space-x-4 pb-4">
                                <div className="bg-blue-100 p-3 rounded-lg">
                                     <FolderKanban className="h-6 w-6 text-blue-600" />
                                </div>
                                <CardTitle className="text-xl font-semibold text-gray-900 group-hover:text-blue-700 transition-colors">
                                    {p.name}
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="flex-grow">
                                <CardDescription className="text-gray-600">
                                    Manage agents, workflows, and settings for this project.
                                </CardDescription>
                            </CardContent>
                            <CardFooter className="flex justify-end items-center text-blue-600 font-medium pt-4 border-t border-gray-100">
                                View Project
                                <ArrowRight className="ml-2 h-4 w-4 transform group-hover:translate-x-1 transition-transform" />
                            </CardFooter>
                        </Card>
                    </Link>
                </li>
            ))}
        </ul>
    );

    const renderContent = () => {
        if (pageLoadingState === 'session_init' || (pageLoadingState === 'loading_projects' && projects.length === 0)) {
            return renderLoadingState();
        }
        if (pageLoadingState === 'error') {
            return renderErrorState();
        }
        if (pageLoadingState === 'projects_loaded' && projects.length === 0 && !isContextLoading) {
            return renderEmptyState();
        }
        if (projects.length > 0) {
            return renderProjectsList();
        }
        // Fallback for cases where context might still be loading but we have some projects (or other edge cases)
        return renderLoadingState();
    };

    return (
        <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white p-4 sm:p-8 lg:p-12">
            <div className="max-w-7xl mx-auto space-y-12">

                {/* Header Section */}
                <div className="flex flex-col sm:flex-row justify-between items-center pb-6 border-b border-gray-200">
                    <div>
                        <h1 className="text-4xl font-bold tracking-tight text-gray-900">Projects Dashboard</h1>
                        <p className="mt-2 text-lg text-gray-600">Create, view, and manage your AI projects.</p>
                    </div>
                    {isContextLoading && pageLoadingState !== 'loading_projects' && (
                        <div className="mt-4 sm:mt-0 flex items-center space-x-2 text-blue-600 bg-blue-50 px-4 py-2 rounded-full text-sm font-medium">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span>Syncing changes...</span>
                        </div>
                    )}
                </div>

                {/* Create Project Section */}
                <Card className="bg-white shadow-lg border-none rounded-xl overflow-hidden">
                     <CardHeader className="bg-gray-50 p-6 border-b border-gray-100">
                        <CardTitle className="text-2xl font-semibold text-gray-800 flex items-center">
                           <PlusCircle className="mr-3 h-6 w-6 text-blue-500" /> Start a New Project
                        </CardTitle>
                        <CardDescription className="mt-1 text-gray-500">
                            Give your new project a name to get started.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="p-6">
                        <form onSubmit={handleCreateNewProject} className="flex flex-col sm:flex-row gap-4 items-start">
                            <div className="flex-grow w-full">
                                <label htmlFor="projectName" className="sr-only">
                                    Project Name
                                </label>
                                <Input
                                    id="projectName"
                                    placeholder="Enter project name..."
                                    value={newProjectName}
                                    onChange={e => setNewProjectName(e.target.value)}
                                    required
                                    disabled={isInputDisabled}
                                    className="w-full text-base p-4 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                                />
                                 {pageError && pageLoadingState !== 'error' && (
                                    <p className="text-red-600 mt-2 text-sm flex items-center">
                                        <AlertTriangle className="h-4 w-4 mr-1" />
                                        {pageError}
                                    </p>
                                )}
                            </div>
                             <Button
                                type="submit"
                                disabled={isButtonDisabled}
                                size="lg" // Larger button
                                className="w-full sm:w-auto text-base font-semibold shadow-md hover:shadow-lg transition-shadow bg-blue-600 hover:bg-blue-700"
                            >
                                {isCreatingProject ? (
                                    <div className="flex items-center">
                                        <Spinner size={20} />
                                        <span className="ml-2">Creating...</span>
                                    </div>
                                ) : (
                                    "Create Project"
                                )}
                            </Button>
                        </form>
                    </CardContent>
                </Card>

                {/* Projects List Section */}
                 <div className="mt-12">
                    <h2 className="text-2xl font-semibold text-gray-900 mb-6">Your Existing Projects</h2>
                    {renderContent()}
                </div>

            </div>
        </div>
    );
}
