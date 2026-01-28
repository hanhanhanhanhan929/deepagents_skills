"use client";

/**
 * FastAPI StreamProvider
 * 
 * 自定义的 StreamProvider，直接与 FastAPI Agent SSE 端点通信
 */

import React, {
    createContext,
    useContext,
    ReactNode,
    useState,
    useEffect,
    useCallback,
} from "react";
import { useQueryState } from "nuqs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ArrowRight, Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
    Agent,
    getAgents,
    healthCheck,
    chatStream,
    SSEEvent,
    formatLLMOutput,
    ChatSession,
    getSessions,
    saveSessions,
    createSession as createSessionHelper,
    deleteSession as deleteSessionHelper,
    updateSessionTitle,
} from "@/lib/fastapi-client";

// ============================================================
// 消息类型定义
// ============================================================

export interface ToolCall {
    name: string;
    args: Record<string, unknown>;
    result?: string;
    truncated?: boolean;
    timestamp: number;
}

export interface SkillLoaded {
    skill: string;
    path: string;
    description?: string;
    timestamp: number;
}

export interface TodoItem {
    id: number;
    description: string;
    status: "pending" | "in_progress" | "completed" | "failed";
}

export interface TodoList {
    todos: TodoItem[];
    timestamp: number;
}

/**
 * 内容片段 - 用于按顺序渲染文本和工具调用
 */
export type ContentSegment =
    | { type: "text"; content: string }
    | { type: "tool"; toolCall: ToolCall };

export interface ChatMessage {
    id: string;
    type: "human" | "ai";
    content: string;
    timestamp: number;
    toolCalls?: ToolCall[];
    skills?: SkillLoaded[];
    todos?: TodoList[];
    error?: string;
    isStreaming?: boolean;
    /** 按顺序排列的内容片段 (文本 + 工具调用交织) */
    segments?: ContentSegment[];
}

export interface FastAPIStreamContextType {
    // 状态
    messages: ChatMessage[];
    isLoading: boolean;
    error: Error | null;
    threadId: string | null;

    // Agent 信息
    agents: Agent[];
    currentAgent: Agent | null;

    // 会话管理
    sessions: ChatSession[];
    selectSession: (sessionId: string) => void;
    deleteSession: (sessionId: string) => void;
    newSession: (agentId?: string) => void;

    // 方法
    submit: (message: string) => Promise<void>;
    stop: () => void;
    setCurrentAgent: (agent: Agent) => void;
    clearMessages: () => void;
}

const FastAPIStreamContext = createContext<FastAPIStreamContextType | undefined>(undefined);

// ... (StreamSession component parts)

function StreamSession({
    children,
    apiUrl,
    initialAgent,
}: {
    children: ReactNode;
    apiUrl: string;
    initialAgent: Agent;
}) {
    const [threadId, setThreadId] = useQueryState("threadId");
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<Error | null>(null);
    const [agents, setAgents] = useState<Agent[]>([initialAgent]);
    const [currentAgent, setCurrentAgent] = useState<Agent>(initialAgent);
    const [abortController, setAbortController] = useState<AbortController | null>(null);

    // 会话状态
    const [sessions, setSessions] = useState<ChatSession[]>([]);

    // 加载 Agent 列表
    useEffect(() => {
        getAgents()
            .then(setAgents)
            .catch(console.error);
    }, []);

    // 加载会话列表
    useEffect(() => {
        setSessions(getSessions());
    }, []);

    // 初始化 threadId
    useEffect(() => {
        if (!threadId) {
            // 如果没有 URL 参数，创建一个新会话
            const newSess = createSessionHelper(initialAgent.id);
            setSessions(getSessions()); // 刷新列表
            setThreadId(newSess.threadId);
        }
    }, [threadId, setThreadId, initialAgent.id]);

    const selectSession = useCallback((sessionId: string) => {
        const session = sessions.find(s => s.id === sessionId);
        if (session) {
            setThreadId(session.threadId);
            setMessages([]); // 这里应该从后端加载历史记录，但目前我们先清空当前视图
            // TODO: 如果后端支持加载历史，应该在这里调用
        }
    }, [sessions, setThreadId]);

    const deleteSession = useCallback((sessionId: string) => {
        deleteSessionHelper(sessionId);
        setSessions(getSessions());
        // 如果删除的是当前会话，创建一个新的
        const currentSession = sessions.find(s => s.threadId === threadId);
        if (currentSession && currentSession.id === sessionId) {
            const newSess = createSessionHelper(currentAgent?.id || "alert_noise_reduction");
            setSessions(getSessions());
            setThreadId(newSess.threadId);
            setMessages([]);
        }
    }, [sessions, threadId, currentAgent]);

    const newSession = useCallback((agentId?: string) => {
        const newSess = createSessionHelper(agentId || currentAgent?.id || "alert_noise_reduction");
        setSessions(getSessions());
        setThreadId(newSess.threadId);
        setMessages([]);
    }, [currentAgent, setThreadId]);

    // 检查服务状态
    useEffect(() => {
        healthCheck().then((ok) => {
            if (!ok) {
                toast.error("无法连接到 FastAPI 服务", {
                    description: `请确保服务运行在 ${apiUrl}`,
                    duration: 10000,
                    richColors: true,
                    closeButton: true,
                });
            }
        });
    }, [apiUrl]);

    const stop = useCallback(() => {
        if (abortController) {
            abortController.abort();
            setAbortController(null);
            setIsLoading(false);
        }
    }, [abortController]);

    const clearMessages = useCallback(() => {
        setMessages([]);
        // 不再生成新的 threadId，而是清除当前屏幕，或者可以保留 threadId
        // 原有逻辑是生成新 threadId，等同于 newSession
        newSession();
    }, [newSession]);

    const submit = useCallback(async (message: string) => {
        if (!message.trim() || isLoading || !currentAgent || !threadId) return;

        setError(null);
        setIsLoading(true);

        // 更新会话标题 (如果是第一条消息或默认标题)
        const currentSession = sessions.find(s => s.threadId === threadId);
        if (currentSession) {
            // 简单判定：如果当前没有任何消息，或者是新会话
            if (messages.length === 0 || currentSession.title === "New Chat") {
                updateSessionTitle(currentSession.id, message);
                setSessions(getSessions());
            }
        }

        const controller = new AbortController();
        setAbortController(controller);

        // 添加用户消息
        const userMessage: ChatMessage = {
            id: crypto.randomUUID(),
            type: "human",
            content: message,
            timestamp: Date.now(),
        };

        // 添加 AI 消息占位
        const assistantMessage: ChatMessage = {
            id: crypto.randomUUID(),
            type: "ai",
            content: "",
            timestamp: Date.now(),
            toolCalls: [],
            skills: [],
            todos: [],
            segments: [],
            isStreaming: true,
        };

        setMessages(prev => [...prev, userMessage, assistantMessage]);

        try {
            const activeTools: Record<string, string> = {};
            let currentTodos: TodoItem[] = [];

            for await (const event of chatStream(currentAgent.id, message, threadId)) {
                if (controller.signal.aborted) break;

                handleSSEEvent(event, assistantMessage, activeTools, currentTodos, (updatedMsg, updatedTodos) => {
                    currentTodos = updatedTodos;
                    setMessages(prev => {
                        const newMessages = [...prev];
                        const lastIndex = newMessages.length - 1;
                        if (lastIndex >= 0 && newMessages[lastIndex].type === "ai") {
                            newMessages[lastIndex] = { ...updatedMsg };
                        }
                        return newMessages;
                    });
                });
            }

            // 完成流式传输
            setMessages(prev => {
                const newMessages = [...prev];
                const lastIndex = newMessages.length - 1;
                if (lastIndex >= 0 && newMessages[lastIndex].type === "ai") {
                    newMessages[lastIndex] = {
                        ...newMessages[lastIndex],
                        isStreaming: false,
                    };
                }
                return newMessages;
            });

        } catch (err) {
            if ((err as Error).name !== 'AbortError') {
                const error = err as Error;
                setError(error);
                toast.error("发生错误", {
                    description: error.message,
                    richColors: true,
                    closeButton: true,
                });
            }
        } finally {
            setIsLoading(false);
            setAbortController(null);
        }
    }, [currentAgent, threadId, isLoading, sessions, messages.length]);

    const value: FastAPIStreamContextType = {
        messages,
        isLoading,
        error,
        threadId,
        agents,
        currentAgent,
        sessions,
        selectSession,
        deleteSession,
        newSession,
        submit,
        stop,
        setCurrentAgent,
        clearMessages,
    };

    return (
        <FastAPIStreamContext.Provider value={value}>
            {children}
        </FastAPIStreamContext.Provider>
    );
}

// ============================================================
// SSE 事件处理
// ============================================================

function handleSSEEvent(
    event: SSEEvent,
    msg: ChatMessage,
    activeTools: Record<string, string>,
    currentTodos: TodoItem[],
    onUpdate: (msg: ChatMessage, todos: TodoItem[]) => void
) {
    const { event: eventType, data } = event;

    // 确保 segments 存在
    if (!msg.segments) msg.segments = [];

    switch (eventType) {
        case "message:chunk": {
            // 应用格式化修复 tokenizer 空格问题
            const formattedChunk = data;
            msg.content += formattedChunk;
            msg.content = formatLLMOutput(msg.content);

            // 更新 segments：合并到最后一个 text segment 或创建新的
            const lastSegment = msg.segments[msg.segments.length - 1];
            if (lastSegment && lastSegment.type === "text") {
                lastSegment.content = formatLLMOutput(lastSegment.content + formattedChunk);
            } else {
                msg.segments.push({ type: "text", content: formattedChunk });
            }

            onUpdate(msg, currentTodos);
            break;
        }

        case "metadata":
            // 可以提取 thread_id 和 agent_id
            break;

        case "tool:start": {
            try {
                const payload = JSON.parse(data);
                const newToolCall: ToolCall = {
                    name: payload.tool,
                    args: payload.args || {},
                    timestamp: Date.now(),
                };

                if (!msg.toolCalls) msg.toolCalls = [];
                msg.toolCalls.push(newToolCall);

                // 添加到 segments（工具调用片段）
                msg.segments.push({ type: "tool", toolCall: newToolCall });

                onUpdate(msg, currentTodos);
            } catch (e) {
                console.warn("Failed to parse tool:start", e);
            }
            break;
        }

        case "tool:result": {
            try {
                const payload = JSON.parse(data);
                const toolCall = msg.toolCalls?.find(
                    tc => tc.name === payload.tool && !tc.result
                );
                if (toolCall) {
                    toolCall.result = payload.result;
                    toolCall.truncated = payload.truncated;
                    onUpdate(msg, currentTodos);
                }
            } catch (e) {
                console.warn("Failed to parse tool:result", e);
            }
            break;
        }

        case "todo:created": {
            try {
                const payload = JSON.parse(data);
                if (!msg.todos) msg.todos = [];
                if (msg.todos.length === 0) {
                    msg.todos.push({ todos: [], timestamp: Date.now() });
                }
                const todoList = msg.todos[0];
                if (todoList && payload.todos) {
                    payload.todos.forEach((desc: string) => {
                        const newTodo: TodoItem = {
                            id: todoList.todos.length,
                            description: desc,
                            status: "pending",
                        };
                        todoList.todos.push(newTodo);
                        currentTodos.push(newTodo);
                    });
                    onUpdate(msg, currentTodos);
                }
            } catch (e) {
                console.warn("Failed to parse todo:created", e);
            }
            break;
        }

        case "todo:updated": {
            try {
                const payload = JSON.parse(data);
                if (msg.todos && msg.todos.length > 0) {
                    const todoList = msg.todos[0];
                    if (todoList) {
                        const item = todoList.todos[payload.todo_id];
                        if (item) {
                            item.status = payload.status;
                            currentTodos[payload.todo_id] = item;
                            onUpdate(msg, currentTodos);
                        }
                    }
                }
            } catch (e) {
                console.warn("Failed to parse todo:updated", e);
            }
            break;
        }

        case "skill:loaded": {
            try {
                const payload = JSON.parse(data);
                if (!msg.skills) msg.skills = [];
                msg.skills.push({
                    skill: payload.skill,
                    path: payload.path,
                    description: payload.description,
                    timestamp: Date.now(),
                });
                onUpdate(msg, currentTodos);
            } catch (e) {
                console.warn("Failed to parse skill:loaded", e);
            }
            break;
        }

        case "error": {
            try {
                const payload = JSON.parse(data);
                msg.error = payload.error;
                onUpdate(msg, currentTodos);
            } catch (e) {
                console.warn("Failed to parse error", e);
            }
            break;
        }

        case "done":
            msg.isStreaming = false;
            onUpdate(msg, currentTodos);
            break;
    }
}

// ============================================================
// 配置表单
// ============================================================

const DEFAULT_API_URL = "http://localhost:8001";
const DEFAULT_AGENT_ID = "alert_noise_reduction";

export function FastAPIStreamProvider({ children }: { children: ReactNode }) {
    const envApiUrl = process.env.NEXT_PUBLIC_API_URL;
    const envAgentId = process.env.NEXT_PUBLIC_DEFAULT_AGENT;

    const [apiUrl, setApiUrl] = useQueryState("apiUrl", {
        defaultValue: envApiUrl || "",
    });
    const [agentId, setAgentId] = useQueryState("agentId", {
        defaultValue: envAgentId || "",
    });

    const [agents, setAgents] = useState<Agent[]>([]);
    const [isLoadingAgents, setIsLoadingAgents] = useState(false);
    const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);

    // 当有 apiUrl 时尝试加载 agents
    useEffect(() => {
        if (apiUrl) {
            setIsLoadingAgents(true);
            getAgents()
                .then((loadedAgents) => {
                    setAgents(loadedAgents);
                    // 自动选择匹配的 agent 或第一个
                    const targetAgent = agentId
                        ? loadedAgents.find(a => a.id === agentId)
                        : loadedAgents[0];
                    if (targetAgent) {
                        setSelectedAgent(targetAgent);
                    }
                })
                .catch((err) => {
                    console.error("Failed to load agents:", err);
                    toast.error("无法加载 Agent 列表", {
                        description: "请检查服务是否运行",
                    });
                })
                .finally(() => setIsLoadingAgents(false));
        }
    }, [apiUrl, agentId]);

    // 如果缺少必要配置，显示配置表单
    if (!apiUrl || !selectedAgent) {
        return (
            <div className="flex items-center justify-center min-h-screen w-full p-4">
                <div className="animate-in fade-in-0 zoom-in-95 flex flex-col border bg-background shadow-lg rounded-lg max-w-xl w-full">
                    <div className="flex flex-col gap-2 mt-10 p-6 border-b">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center">
                                <span className="text-xl">⚡️</span>
                            </div>
                            <h1 className="text-xl font-semibold tracking-tight">
                                Deep Agents Chat
                            </h1>
                        </div>
                        <p className="text-muted-foreground text-sm mt-2">
                            连接到你的 FastAPI Agent 服务开始对话
                        </p>
                    </div>

                    <form
                        onSubmit={(e) => {
                            e.preventDefault();
                            const form = e.target as HTMLFormElement;
                            const formData = new FormData(form);
                            const url = formData.get("apiUrl") as string;
                            const agent = formData.get("agentId") as string;
                            setApiUrl(url);
                            setAgentId(agent);
                        }}
                        className="flex flex-col gap-5 p-6 bg-muted/50"
                    >
                        <div className="flex flex-col gap-2">
                            <Label htmlFor="apiUrl">
                                API URL <span className="text-rose-500">*</span>
                            </Label>
                            <p className="text-muted-foreground text-xs">
                                FastAPI 服务地址
                            </p>
                            <Input
                                id="apiUrl"
                                name="apiUrl"
                                className="bg-background"
                                defaultValue={apiUrl || DEFAULT_API_URL}
                                placeholder="http://localhost:8001"
                                required
                            />
                        </div>

                        {isLoadingAgents ? (
                            <div className="flex items-center gap-2 text-muted-foreground">
                                <Loader2 className="w-4 h-4 animate-spin" />
                                <span>加载 Agent 列表...</span>
                            </div>
                        ) : agents.length > 0 ? (
                            <div className="flex flex-col gap-2">
                                <Label>选择 Agent <span className="text-rose-500">*</span></Label>
                                <div className="grid gap-2">
                                    {agents.map((agent) => (
                                        <label
                                            key={agent.id}
                                            className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${selectedAgent?.id === agent.id
                                                ? "border-indigo-500 bg-indigo-50"
                                                : "hover:bg-muted"
                                                }`}
                                        >
                                            <input
                                                type="radio"
                                                name="agentId"
                                                value={agent.id}
                                                checked={selectedAgent?.id === agent.id}
                                                onChange={() => setSelectedAgent(agent)}
                                                className="sr-only"
                                            />
                                            <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-white text-sm font-bold">
                                                {agent.id.charAt(0).toUpperCase()}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="font-medium text-sm">{agent.name}</div>
                                                <div className="text-xs text-muted-foreground truncate">
                                                    {agent.description}
                                                </div>
                                            </div>
                                        </label>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div className="flex flex-col gap-2">
                                <Label htmlFor="agentIdInput">
                                    Agent ID <span className="text-rose-500">*</span>
                                </Label>
                                <Input
                                    id="agentIdInput"
                                    name="agentId"
                                    className="bg-background"
                                    defaultValue={agentId || DEFAULT_AGENT_ID}
                                    placeholder="alert_noise_reduction"
                                    required
                                />
                            </div>
                        )}

                        <div className="flex justify-end mt-2">
                            <Button type="submit" size="lg" disabled={!selectedAgent && agents.length > 0}>
                                开始对话
                                <ArrowRight className="w-5 h-5 ml-2" />
                            </Button>
                        </div>
                    </form>
                </div>
            </div>
        );
    }

    return (
        <StreamSession apiUrl={apiUrl} initialAgent={selectedAgent}>
            {children}
        </StreamSession>
    );
}

// ============================================================
// Hook
// ============================================================

export function useFastAPIStream(): FastAPIStreamContextType {
    const context = useContext(FastAPIStreamContext);
    if (context === undefined) {
        throw new Error("useFastAPIStream must be used within FastAPIStreamProvider");
    }
    return context;
}

export default FastAPIStreamContext;
