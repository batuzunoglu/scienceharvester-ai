// frontend/src/app/projects/page.tsx
// Cache-breaking comment - attempt 2 (just to be sure)
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

    // Ref to track if a fetch has been *initiated* for a specific session ID
    // to prevent re-fetching while one is already in progress or if already fetched.
    const fetchInitiatedForSession = useRef<string | null>(null);

    // Effect 1: Establish userSessionId (Runs ONCE on mount to get/set the ID)
    useEffect(() => {
        console.log("ProjectsPage - Effect 1: Running to establish session ID.");
        let sessionIdFromStorage = localStorage.getItem('user_session_id');
        if (!sessionIdFromStorage) {
            sessionIdFromStorage = Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
            localStorage.setItem('user_session_id', sessionIdFromStorage);
            console.log("ProjectsPage - Effect 1: New session ID generated:", sessionIdFromStorage);
        } else {
            console.log("ProjectsPage - Effect 1: Existing session ID found:", sessionIdFromStorage);
        }
        // Only set if it's actually different to avoid an unnecessary re-render loop
        if (userSessionId !== sessionIdFromStorage) {
            setUserSessionId(sessionIdFromStorage);
            console.log("ProjectsPage - Effect 1: Setting userSessionId state to:", sessionIdFromStorage);
        }
    }, []); // Empty dependency array: runs only once on component mount.

    // Effect 2: Load projects when userSessionId is available or fetchProjects (the function itself) changes.
    useEffect(() => {
        console.log(`ProjectsPage - Effect 2: Evaluating. userSessionId: ${userSessionId}, fetchInitiatedForSession: ${fetchInitiatedForSession.current}, isContextLoading: ${isContextLoading}, projects.length: ${projects.length}`);

        // Guard: Only proceed if userSessionId is available.
        if (!userSessionId) {
            console.log("ProjectsPage - Effect 2: No userSessionId. Setting state to 'session_init'.");
            setPageLoadingState('session_init');
            fetchInitiatedForSession.current = null; // Reset tracking if session is lost/not set
            return;
        }

        // Guard: If a fetch has already been initiated for the current userSessionId, don't do it again.
        // This also handles the case where projects might already be loaded (e.g., from context cache after navigation)
        // and the state just needs to be updated to 'projects_loaded'.
        if (fetchInitiatedForSession.current === userSessionId) {
            console.log(`ProjectsPage - Effect 2: Fetch already initiated or completed for session ${userSessionId}.`);
            // If projects are loaded and state isn't 'projects_loaded' or 'error', set it.
            if (projects.length > 0 && pageLoadingState !== 'projects_loaded' && pageLoadingState !== 'error') {
                console.log("ProjectsPage - Effect 2: Projects found, setting state to 'projects_loaded'.");
                setPageLoadingState('projects_loaded');
            } else if (projects.length === 0 && pageLoadingState === 'loading_projects' && !isContextLoading) {
                // If still 'loading_projects' but context says not loading and no projects, it's an empty state.
                console.log("ProjectsPage - Effect 2: No projects, context not loading, setting state to 'projects_loaded' (for empty state).");
                setPageLoadingState('projects_loaded');
            } else if (pageLoadingState === 'error') {
                 console.log("ProjectsPage - Effect 2: State is 'error', not changing.");
            } else if (pageLoadingState !== 'projects_loaded' && pageLoadingState !== 'error' && !isContextLoading && projects.length === 0) {
                console.log("ProjectsPage - Effect 2: Defaulting to 'projects_loaded' for empty state if not loading.");
                setPageLoadingState('projects_loaded');
            }
            return;
        }

        // If we reach here, it means userSessionId is present and we haven't initiated a fetch for it yet.
        console.log(`ProjectsPage - Effect 2: Initiating project load for session ID: ${userSessionId}`);
        fetchInitiatedForSession.current = userSessionId; // Mark that fetch is being initiated for this session
        setPageLoadingState('loading_projects');
        setPageError(null);

        const loadProjectsAsync = async (sid: string) => {
            console.log(`ProjectsPage - Effect 2: loadProjectsAsync called for ${sid}`);
            try {
                await fetchProjects(sid); // fetchProjects is from context
                console.log(`ProjectsPage - Effect 2: fetchProjects(sid) completed for session ${sid}.`);
                // Only update page state if the session ID hasn't changed *during* the async fetch
                // and if the fetch wasn't for a now-stale session ID.
                if (fetchInitiatedForSession.current === sid && userSessionId === sid) {
                    setPageLoadingState('projects_loaded');
                    console.log(`ProjectsPage - Effect 2: State set to 'projects_loaded' for session ${sid}.`);
                } else {
                    console.log(`ProjectsPage - Effect 2: Session ID changed or fetch was for stale session during/after fetch. Current session: ${userSessionId}, Fetched for: ${sid}, Initiated for: ${fetchInitiatedForSession.current}. Not updating page state for old session.`);
                }
            } catch (err) {
                console.error("ProjectsPage - Effect 2: Failed to load projects:", err);
                // Only update page state if the error belongs to the currently active session initiation
                if (fetchInitiatedForSession.current === sid && userSessionId === sid) {
                    setPageError((err as Error).message || "Could not load projects. Please try again later.");
                    setPageLoadingState('error');
                    console.log(`ProjectsPage - Effect 2: State set to 'error' for session ${sid}.`);
                } else {
                    console.log(`ProjectsPage - Effect 2: Error occurred for session ${sid}, but session ID changed or fetch was stale. Current session: ${userSessionId}, Error for: ${sid}, Initiated for: ${fetchInitiatedForSession.current}. Not updating page state for old session's error.`);
                }
            }
        };

        loadProjectsAsync(userSessionId);

    // Dependencies:
    // - userSessionId: Triggers when the session ID is set or changes.
    // - fetchProjects: Triggers if the fetchProjects function reference from context changes (should be stable with useCallback).
    // - projects: Re-evaluate if the projects array itself changes (e.g., from cache update or another component).
    // - isContextLoading: If the context's loading state changes, we might need to update our page's loading state.
    //
    // Removing `pageLoadingState` from deps is key to avoid loops with `setPageLoadingState` inside.
    }, [userSessionId, fetchProjects, projects, isContextLoading]);


    // --- Handlers ---
    const handleCreateNewProject = async (e: React.FormEvent) => {
        e.preventDefault();
        console.log("ProjectsPage: handleCreateNewProject triggered");
        setPageError(null);
        const trimmedName = newProjectName.trim();
        if (!trimmedName || !userSessionId) {
            const errorMsg = !trimmedName ? "Project name cannot be empty." : "User session not available. Please refresh.";
            console.error("ProjectsPage: Create project validation error:", errorMsg);
            setPageError(errorMsg);
            return;
        }
        setIsCreatingProject(true);
        try {
            console.log("ProjectsPage: Calling createProject from context with name:", trimmedName, "sessionId:", userSessionId);
            const newProject = await createProject(trimmedName, userSessionId);
            if (newProject && newProject.id) {
                console.log("ProjectsPage: Project created successfully:", newProject.id);
                setNewProjectName('');
                router.push(`/projects/${newProject.id}/agent1`);
            } else {
                console.error("ProjectsPage: Project creation returned invalid data:", newProject);
                throw new Error("Project creation returned invalid data.");
            }
        } catch (err) {
            console.error("ProjectsPage: Error creating project:", err);
            setPageError((err as Error).message || "Failed to create project.");
        } finally {
            setIsCreatingProject(false);
        }
    };

    // --- Derived State ---
    const isInputDisabled = isCreatingProject || isContextLoading || pageLoadingState === 'loading_projects' || pageLoadingState === 'session_init';
    const isButtonDisabled = isInputDisabled || !newProjectName.trim() || !userSessionId;

    // --- Render Logic ---
    const renderLoadingState = () => {
        const message = pageLoadingState === 'session_init' || !userSessionId
            ? 'Initializing Session...'
            : 'Loading Your Projects...';
        console.log("ProjectsPage: Rendering Loading State - ", message);
        return (
            <div className="flex flex-col items-center justify-center text-center py-24 bg-white rounded-xl shadow-sm border border-gray-100">
                <Loader2 className="h-16 w-16 text-blue-500 animate-spin" />
                <p className="mt-6 text-xl font-medium text-gray-700">{message}</p>
                <p className="mt-2 text-base text-gray-500">Hang tight, we are getting things ready for you.</p>
            </div>
        );
    };

    const renderErrorState = () => {
        console.log("ProjectsPage: Rendering Error State - ", pageError);
        return (
            <Alert variant="destructive" className="py-8 text-center bg-red-50 border-red-200">
                <ServerCrash className="h-12 w-12 mx-auto text-red-500" />
                <AlertTitle className="text-xl font-bold mt-4">Load Error!</AlertTitle>
                <AlertDescription className="text-base mt-2">
                    {pageError || "We couldn't load your projects. Please check your connection and try again."}
                </AlertDescription>
                <Button
                    variant="destructive"
                    className="mt-6"
                    onClick={() => {
                        if (userSessionId) {
                            console.log("ProjectsPage: Retry button clicked. Resetting fetchInitiated and calling fetchProjects.");
                            fetchInitiatedForSession.current = null; // Allow re-fetch
                            // Force re-trigger of useEffect by briefly clearing userSessionId or a dedicated retry state
                            // However, the effect should re-run if userSessionId is already set and fetchInitiated is null.
                            // Let's just call fetchProjects, the effect should then pick up the state change.
                            setPageLoadingState('loading_projects'); // Show loading
                            fetchProjects(userSessionId)
                                .then(() => {
                                    // If fetchProjects in context updates 'projects' or 'isLoading',
                                    // Effect 2 should naturally update pageLoadingState to 'projects_loaded'
                                    // if (fetchInitiatedForSession.current === userSessionId) { // ensure it's still the same session
                                    //     setPageLoadingState('projects_loaded');
                                    // }
                                })
                                .catch(err => {
                                    // if (fetchInitiatedForSession.current === userSessionId) {
                                    //     setPageError((err as Error).message || "Retry failed.");
                                    //     setPageLoadingState('error');
                                    // }
                                });
                        }
                    }}
                    disabled={isContextLoading || !userSessionId || pageLoadingState === 'loading_projects'}
                >
                    {(isContextLoading || pageLoadingState === 'loading_projects') ? <Spinner size={16} /> : 'Retry Loading'}
                </Button>
            </Alert>
        );
    };

    const renderEmptyState = () => {
        console.log("ProjectsPage: Rendering Empty State.");
        return (
            <div className="text-center py-24 border-2 border-dashed border-gray-300 rounded-xl bg-gray-50">
                <Inbox className="mx-auto h-16 w-16 text-gray-400" />
                <h3 className="mt-4 text-xl font-semibold text-gray-900">Your workspace is empty!</h3>
                <p className="mt-2 text-base text-gray-500">Looks like you haven't created any projects yet.</p>
                <p className="mt-1 text-base text-gray-500">Use the form above to start your first project.</p>
            </div>
        );
    };

    const renderProjectsList = () => {
        console.log("ProjectsPage: Rendering Projects List with", projects.length, "projects.");
        return (
            <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {projects.map(p => (
                    <li key={p.id}>
                        <Link href={`/projects/${p.id}/agent1`} passHref legacyBehavior>
                            <a className="group block h-full">
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
                            </a>
                        </Link>
                    </li>
                ))}
            </ul>
        );
    };

    const renderContent = () => {
        console.log(`ProjectsPage: renderContent called. pageLoadingState: ${pageLoadingState}, projects.length: ${projects.length}, isContextLoading: ${isContextLoading}`);
        if (pageLoadingState === 'session_init' || (!userSessionId && pageLoadingState !== 'error')) {
            return renderLoadingState();
        }
        if (pageLoadingState === 'loading_projects' && !pageError) { // Show loading as long as we are in this state without an error
             return renderLoadingState();
        }
        if (pageLoadingState === 'error') {
            return renderErrorState();
        }
        // If projects are loaded (or context isn't loading anymore and we have 0 projects from a previous successful fetch)
        if (pageLoadingState === 'projects_loaded' && projects.length === 0 && !isContextLoading) {
            return renderEmptyState();
        }
        if (projects.length > 0) { // Can be true even if pageLoadingState is 'loading_projects' if projects were loaded from cache
            return renderProjectsList();
        }
        // Fallback loading state if none of the above conditions are met but we are not in an error state
        // This might catch edge cases where `isContextLoading` is true but `pageLoadingState` hasn't caught up.
        if (isContextLoading) return renderLoadingState();

        // If projects loaded, 0 projects, not context loading, and somehow not caught by empty state (should be)
        if (pageLoadingState === 'projects_loaded' && projects.length === 0) return renderEmptyState();

        return renderLoadingState(); // Default fallback
    };

    console.log(`ProjectsPage: Rendering component. userSessionId: ${userSessionId}, pageLoadingState: ${pageLoadingState}, isContextLoading: ${isContextLoading}, projects:`, projects.length);

    return (
        <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white p-4 sm:p-8 lg:p-12">
            <div className="max-w-7xl mx-auto space-y-12">

                {/* Header Section */}
                <div className="flex flex-col sm:flex-row justify-between items-center pb-6 border-b border-gray-200">
                    <div>
                        <h1 className="text-4xl font-bold tracking-tight text-gray-900">Projects Dashboard</h1>
                        <p className="mt-2 text-lg text-gray-600">Create, view, and manage your AI projects.</p>
                    </div>
                    {isContextLoading && pageLoadingState !== 'loading_projects' && pageLoadingState !== 'session_init' && (
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
                                {pageError && pageLoadingState !== 'error' && ( // Only show this secondary error if not already in main error state
                                    <p className="text-red-600 mt-2 text-sm flex items-center">
                                        <AlertTriangle className="h-4 w-4 mr-1" />
                                        {pageError}
                                    </p>
                                )}
                            </div>
                            <Button
                                type="submit"
                                disabled={isButtonDisabled}
                                size="lg"
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
