import { useState, useEffect } from 'react';
import { MessageSquare, Upload, FileText, RefreshCw, Search, Brain, Shield, Zap, X, Database, Code, Layers, Key, BarChart3, FileSearch, Hash } from 'lucide-react';

interface Session {
  id: string;
  name: string;
  created_at: string;
  session_id?: string; // Optional for backward compatibility
}

interface Activity {
  id: string;
  type: 'session' | 'upload' | 'document' | 'query' | 'enrich' | 'retrieve' | 'mask' | 'response' | string;
  message: string;
  timestamp: Date;
  sessionId: string;
  status?: 'pending' | 'in-progress' | 'completed' | 'error';
}

interface ProcessStep {
  step: string;
  status: 'pending' | 'in-progress' | 'completed' | 'error';
  message: string;
  timestamp: Date;
}

interface ActivityLogProps {
  currentSessionId?: string | null;
  sessions?: Session[];
  currentProcess?: ProcessStep[];
  isProcessing?: boolean;
  onClose?: () => void;
}

export default function ActivityLog({ currentSessionId, sessions = [], currentProcess = [], isProcessing = false, onClose }: ActivityLogProps) {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [processHistory, setProcessHistory] = useState<ProcessStep[]>([]);

  // Load process history from sessionStorage on component mount
  useEffect(() => {
    const savedHistory = sessionStorage.getItem(`processHistory_${currentSessionId || 'global'}`);
    if (savedHistory) {
      try {
        const parsed = JSON.parse(savedHistory);
        // Convert timestamp strings back to Date objects
        const processHistoryWithDates = parsed.map((step: any) => ({
          ...step,
          timestamp: new Date(step.timestamp)
        }));
        setProcessHistory(processHistoryWithDates);
      } catch (error) {
        console.error('Failed to parse process history:', error);
      }
    }
  }, [currentSessionId]);

  // Save process history to sessionStorage whenever it changes
  useEffect(() => {
    if (processHistory.length > 0) {
      sessionStorage.setItem(`processHistory_${currentSessionId || 'global'}`, JSON.stringify(processHistory));
    }
  }, [processHistory, currentSessionId]);

  // Store completed processes in history
  useEffect(() => {
    if (!isProcessing && currentProcess.length > 0) {
      // Only add to history if all steps are completed or some failed
      const hasCompletedSteps = currentProcess.some(step => step.status === 'completed');
      const hasErrorSteps = currentProcess.some(step => step.status === 'error');
      
      if (hasCompletedSteps || hasErrorSteps) {
        setProcessHistory(prev => {
          // Add new steps to history, avoiding duplicates
          const newSteps = currentProcess.filter(step => 
            !prev.some(histStep => 
              histStep.step === step.step && 
              histStep.message === step.message && 
              Math.abs(histStep.timestamp.getTime() - step.timestamp.getTime()) < 1000
            )
          );
          return [...newSteps, ...prev].slice(0, 20); // Keep last 20 steps
        });
      }
    }
  }, [isProcessing, currentProcess]);

  const clearProcessHistory = () => {
    setProcessHistory([]);
    sessionStorage.removeItem(`processHistory_${currentSessionId || 'global'}`);
  };

  useEffect(() => {
    // Generate activity data based on sessions
    setIsLoading(true);
    
    if (sessions.length === 0) {
      setActivities([]);
      setIsLoading(false);
      return;
    }
    
    // Create a list of activities from sessions data
    const allActivities: Activity[] = [];
    
    // Add session creation activities
    sessions.forEach(session => {
      // Session creation activity
      allActivities.push({
        id: `session-${session.id}`,
        type: 'session',
        message: `Created conversation: ${session.name}`,
        timestamp: new Date(session.created_at),
        sessionId: session.session_id || session.id,
        status: 'completed'
      });
    });
    
    // Sort activities by timestamp (newest first)
    allActivities.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
    
    setActivities(allActivities);
    setIsLoading(false);
  }, [sessions]);

  // Filter activities if a current session is selected
  const filteredActivities = currentSessionId 
    ? activities.filter(activity => activity.sessionId === currentSessionId)
    : activities;

  const getActivityIcon = (type: string, status?: string) => {
    const baseClasses = "w-4 h-4";
    const statusClasses = status === 'in-progress' ? 'animate-spin' : '';
    
    switch (type) {
      // Basic activities
      case 'session': return <MessageSquare className={`${baseClasses} text-purple-500`} />;
      case 'upload': return <Upload className={`${baseClasses} text-green-500 ${statusClasses}`} />;
      case 'document': return <FileText className={`${baseClasses} text-blue-500 ${statusClasses}`} />;
      
      // Query processing
      case 'query': return <Search className={`${baseClasses} text-blue-600`} />;
      case 'original_query': return <Search className={`${baseClasses} text-blue-700`} />;
      case 'enriched_query': return <Brain className={`${baseClasses} text-purple-600`} />;
      case 'enrich': return <Brain className={`${baseClasses} text-purple-600 ${statusClasses}`} />;
      
      // Document retrieval
      case 'retrieve': return <FileSearch className={`${baseClasses} text-green-600 ${statusClasses}`} />;
      case 'retrieved_chunks': return <Layers className={`${baseClasses} text-green-700`} />;
      case 'retrieved_metadata': return <Database className={`${baseClasses} text-cyan-600`} />;
      
      // Privacy & masking
      case 'mask': return <Shield className={`${baseClasses} text-orange-600 ${statusClasses}`} />;
      case 'masked_chunks': return <Shield className={`${baseClasses} text-orange-700`} />;
      case 'masked_response': return <Shield className={`${baseClasses} text-red-600`} />;
      case 'unmasked_response': return <Shield className={`${baseClasses} text-green-600`} />;
      
      // Response generation
      case 'response': return <Zap className={`${baseClasses} text-yellow-600 ${statusClasses}`} />;
      case 'scaled_result': return <BarChart3 className={`${baseClasses} text-blue-500`} />;
      case 'unscaled_result': return <BarChart3 className={`${baseClasses} text-indigo-500`} />;
      
      // Formula & processing
      case 'formula_check': return <Code className={`${baseClasses} text-purple-500`} />;
      case 'processed_docs': return <FileText className={`${baseClasses} text-gray-600`} />;
      
      // Chat log
      case 'chat_log_pending': return <Database className={`${baseClasses} text-orange-500 ${statusClasses}`} />;
      case 'chat_log_id': return <Hash className={`${baseClasses} text-green-500`} />;
      
      // Chunk details
      case 'chunk_detail_0':
      case 'chunk_detail_1': 
      case 'chunk_detail_2': return <Key className={`${baseClasses} text-gray-500`} />;
      
      // Transparency
      case 'transparency': return <RefreshCw className={`${baseClasses} text-gray-400 ${statusClasses}`} />;
      
      // Final status
      case 'final_status': 
        if (status === 'completed') return <Brain className={`${baseClasses} text-green-600`} />;
        if (status === 'error') return <X className={`${baseClasses} text-red-600`} />;
        return <RefreshCw className={`${baseClasses} text-blue-500 ${statusClasses}`} />;
      
      default: return <MessageSquare className={`${baseClasses} text-gray-500`} />;
    }
  };

  // Group process steps by phase for better organization
  const groupProcessSteps = (steps: ProcessStep[]) => {
    const phases = {
      'Query Processing': ['query', 'original_query', 'enriched_query', 'enrich'],
      'Document Retrieval': ['retrieve', 'retrieved_chunks', 'retrieved_metadata', 'chunk_detail_0', 'chunk_detail_1', 'chunk_detail_2'],
      'Privacy & Masking': ['mask', 'masked_chunks', 'masked_response', 'unmasked_response'],
      'Response Generation': ['response', 'scaled_result', 'unscaled_result'],
      'Final Processing': ['formula_check', 'processed_docs', 'chat_log_pending', 'transparency', 'final_status']
    };

    const grouped: Record<string, ProcessStep[]> = {};
    
    Object.entries(phases).forEach(([phaseName, stepTypes]) => {
      grouped[phaseName] = steps.filter(step => stepTypes.includes(step.step));
    });

    return grouped;
  };

  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'completed': return 'bg-green-50 border-green-200';
      case 'in-progress': return 'bg-blue-50 border-blue-200';
      case 'error': return 'bg-red-50 border-red-200';
      case 'pending': return 'bg-gray-50 border-gray-200';
      default: return 'bg-gray-50 border-gray-200';
    }
  };

  const formatTimestamp = (timestamp: Date | undefined) => {
    if (!timestamp) return '';
    return timestamp.toLocaleString();
  };

  return (
    <div className="h-full bg-white flex flex-col">
      <div className="p-3 border-b border-gray-200 flex items-center justify-between">
        <h3 className="font-semibold text-gray-800">Activity Log</h3>
        <div className="flex items-center gap-2">
          {currentSessionId && (
            <span className="text-xs bg-purple-100 text-purple-800 py-1 px-2 rounded-full">
              Filtered by current session
            </span>
          )}
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 hover:bg-gray-100 rounded-md transition-colors"
              title="Close activity log"
            >
              <X className="w-4 h-4 text-gray-500 hover:text-gray-700" />
            </button>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-auto p-3">
        {isLoading ? (
          <div className="text-center py-6">
            <RefreshCw className="w-8 h-8 text-gray-400 mx-auto mb-2 animate-spin" />
            <p className="text-gray-500">Loading activities...</p>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Current Process Steps */}
            {isProcessing && currentProcess.length > 0 && (
              <div className="mb-4">
                <h4 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin text-blue-500" />
                  Current Process
                </h4>
                
                {(() => {
                  const groupedSteps = groupProcessSteps(currentProcess);
                  return Object.entries(groupedSteps).map(([phaseName, steps]) => {
                    if (steps.length === 0) return null;
                    
                    return (
                      <div key={phaseName} className="mb-4">
                        <h5 className="text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wide">
                          {phaseName}
                        </h5>
                        <div className="space-y-2 pl-2 border-l-2 border-gray-200">
                          {steps.map((step, index) => (
                            <div key={`process-${phaseName}-${index}`} className={`flex items-start space-x-3 p-3 rounded-lg border ${getStatusColor(step.status)}`}>
                              <div className="flex-shrink-0 mt-1">
                                {getActivityIcon(step.step, step.status)}
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm text-gray-800 break-words">{step.message}</p>
                                <p className="text-xs text-gray-500 mt-1">
                                  {formatTimestamp(step.timestamp)}
                                </p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  });
                })()}
              </div>
            )}

            {/* Recent Process History */}
            {!isProcessing && processHistory.length > 0 && (
              <div className="mb-4">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-medium text-gray-700 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-green-500" />
                    Recent Process
                  </h4>
                  <button
                    onClick={clearProcessHistory}
                    className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100"
                    title="Clear process history"
                  >
                    <X className="w-3 h-3" />
                    Clear
                  </button>
                </div>
                
                {(() => {
                  const groupedSteps = groupProcessSteps(processHistory.slice(0, 20));
                  return Object.entries(groupedSteps).map(([phaseName, steps]) => {
                    if (steps.length === 0) return null;
                    
                    return (
                      <div key={`history-${phaseName}`} className="mb-4">
                        <h5 className="text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wide">
                          {phaseName}
                        </h5>
                        <div className="space-y-2 pl-2 border-l-2 border-gray-200">
                          {steps.map((step, index) => (
                            <div key={`history-${phaseName}-${index}`} className={`flex items-start space-x-3 p-3 rounded-lg border ${getStatusColor(step.status)}`}>
                              <div className="flex-shrink-0 mt-1">
                                {getActivityIcon(step.step, step.status)}
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm text-gray-800 break-words">{step.message}</p>
                                <p className="text-xs text-gray-500 mt-1">
                                  {formatTimestamp(step.timestamp)}
                                </p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  });
                })()}
              </div>
            )}

            {/* Historical Activities */}
            {filteredActivities.length > 0 && (
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Session History</h4>
                {filteredActivities.map((activity) => (
                  <div key={activity.id} className={`flex items-start space-x-3 p-3 rounded-lg border ${getStatusColor(activity.status)}`}>
                    <div className="flex-shrink-0 mt-1">
                      {getActivityIcon(activity.type, activity.status)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-800">{activity.message}</p>
                      <p className="text-xs text-gray-500 mt-1">
                        {formatTimestamp(activity.timestamp)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Empty State */}
            {filteredActivities.length === 0 && !isProcessing && processHistory.length === 0 && (
              <div className="text-center py-6">
                <MessageSquare className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                <p className="text-gray-500">No activities to display</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
