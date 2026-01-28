"use client";

/**
 * FastAPI Thread 组件
 * 
 * 专为 FastAPI Agent 设计的聊天界面
 */

import { useState, FormEvent, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useFastAPIStream, ChatMessage, ToolCall, SkillLoaded, TodoList, ContentSegment } from "@/providers/FastAPIStream";
import { Button } from "@/components/ui/button";
import {
    ArrowDown,
    LoaderCircle,
    SquarePen,
    ChevronDown,
    Play,
    CheckCircle2,
    Circle,
    BookOpen,
    Sparkles,
    ListTodo,
    Shield,
    MapPin,
    Bot,
    Trash2,
    MessageSquare,
    Plus,
    PanelLeftClose,
    PanelLeft,
    ChevronRight,
} from "lucide-react";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import { MarkdownText } from "./markdown-text";
import { format } from "date-fns";
import { zhCN } from "date-fns/locale";

// ============================================================
// 辅助组件
// ============================================================

function Sidebar() {
    const { sessions, threadId, selectSession, deleteSession, newSession, isLoading } = useFastAPIStream();
    const [isOpen, setIsOpen] = useState(true);

    if (!isOpen) {
        return (
            <div className="border-r bg-slate-50 flex flex-col items-center py-4 gap-4 w-14 shrink-0">
                <Button variant="ghost" size="icon" onClick={() => setIsOpen(true)}>
                    <PanelLeft className="w-5 h-5 text-slate-500" />
                </Button>
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => newSession()}
                    disabled={isLoading}
                    title="新对话"
                >
                    <Plus className="w-5 h-5 text-indigo-600" />
                </Button>
            </div>
        );
    }

    return (
        <div className="w-64 border-r bg-slate-50 flex flex-col h-full shrink-0 transition-all">
            {/* Sidebar Header */}
            <div className="p-4 border-b flex items-center justify-between bg-white/50 backdrop-blur-sm sticky top-0">
                <h2 className="font-semibold text-sm text-slate-700">历史会话</h2>
                <div className="flex items-center gap-1">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => newSession()}
                        disabled={isLoading}
                        title="新对话"
                    >
                        <Plus className="w-4 h-4 text-indigo-600" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setIsOpen(false)}>
                        <PanelLeftClose className="w-4 h-4 text-slate-400" />
                    </Button>
                </div>
            </div>

            {/* Session List */}
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
                {sessions.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-40 text-slate-400 text-xs gap-2">
                        <MessageSquare className="w-8 h-8 opacity-20" />
                        <span>暂无历史记录</span>
                    </div>
                ) : (
                    sessions.map((session) => (
                        <div
                            key={session.id}
                            className={cn(
                                "group flex items-center gap-3 px-3 py-3 rounded-lg cursor-pointer transition-all border border-transparent",
                                session.threadId === threadId
                                    ? "bg-white border-slate-200 shadow-sm text-indigo-700"
                                    : "hover:bg-slate-100 text-slate-600"
                            )}
                            onClick={() => selectSession(session.id)}
                        >
                            <MessageSquare className={cn(
                                "w-4 h-4 shrink-0",
                                session.threadId === threadId ? "text-indigo-500" : "text-slate-400"
                            )} />
                            <div className="flex-1 min-w-0 text-left">
                                <div className="text-sm font-medium truncate leading-tight mb-0.5">
                                    {session.title}
                                </div>
                                <div className="text-[10px] text-slate-400 truncate">
                                    {format(session.updatedAt, "MM-dd HH:mm", { locale: zhCN })}
                                </div>
                            </div>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-slate-200 hover:text-red-500"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    deleteSession(session.id);
                                }}
                            >
                                <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

function StickyToBottomContent(props: {
    content: React.ReactNode;
    footer?: React.ReactNode;
    className?: string;
    contentClassName?: string;
}) {
    const context = useStickToBottomContext();
    return (
        <div
            ref={context.scrollRef}
            style={{ width: "100%", height: "100%" }}
            className={props.className}
        >
            <div ref={context.contentRef} className={props.contentClassName}>
                {props.content}
            </div>
            {props.footer}
        </div>
    );
}

function ScrollToBottom(props: { className?: string }) {
    const { isAtBottom, scrollToBottom } = useStickToBottomContext();
    if (isAtBottom) return null;
    return (
        <Button
            variant="outline"
            className={props.className}
            onClick={() => scrollToBottom()}
        >
            <ArrowDown className="w-4 h-4" />
            <span>滚动到底部</span>
        </Button>
    );
}

// Agent 图标映射
const getAgentIcon = (agentId: string) => {
    const icons: Record<string, typeof Bot> = {
        travel: MapPin,
        sre: Shield,
    };
    return icons[agentId] || Bot;
};

// Agent 颜色映射
const getAgentColor = (agentId: string) => {
    const colors: Record<string, { bg: string; text: string }> = {
        travel: { bg: "bg-indigo-600", text: "text-indigo-600" },
        sre: { bg: "bg-emerald-600", text: "text-emerald-600" },
    };
    return colors[agentId] || { bg: "bg-slate-600", text: "text-slate-600" };
};

// ============================================================
// 消息组件
// ============================================================

function HumanMessageBubble({ message }: { message: ChatMessage }) {
    return (
        <div className="flex items-start justify-end gap-2 group">
            <div className="flex flex-col gap-2">
                <p className="px-4 py-2 rounded-3xl bg-muted w-fit ml-auto whitespace-pre-wrap max-w-xl">
                    {message.content}
                </p>
            </div>
        </div>
    );
}

function TodoListView({ todos }: { todos: TodoList[] }) {
    if (!todos || todos.length === 0) return null;

    return (
        <div className="mb-4 bg-amber-50 rounded-xl p-4 border border-amber-100/50">
            <div className="flex items-center gap-2 mb-3 text-amber-700 font-bold text-xs uppercase tracking-wide opacity-80">
                <ListTodo className="w-4 h-4" />
                <span>任务计划</span>
            </div>
            {todos.map((list, ti) => (
                <div key={ti} className="space-y-2">
                    {list.todos.map((todo) => (
                        <div
                            key={todo.id}
                            className={cn(
                                "flex items-start gap-3 text-sm transition-all",
                                todo.status === "completed" ? "text-slate-400 line-through" : "text-slate-700"
                            )}
                        >
                            <div className="mt-0.5">
                                {todo.status === "completed" ? (
                                    <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                ) : todo.status === "in_progress" ? (
                                    <LoaderCircle className="w-4 h-4 text-indigo-500 animate-spin" />
                                ) : (
                                    <Circle className="w-4 h-4 text-slate-300" />
                                )}
                            </div>
                            <span className="leading-relaxed">{todo.description}</span>
                        </div>
                    ))}
                </div>
            ))}
        </div>
    );
}

function SkillsView({ skills }: { skills: SkillLoaded[] }) {
    if (!skills || skills.length === 0) return null;

    const formatSkillName = (name: string) => {
        return name.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(" ");
    };

    return (
        <div className="mb-4 bg-violet-50 rounded-xl p-4 border border-violet-100/50">
            <div className="flex items-center gap-2 mb-3 text-violet-700 font-bold text-xs uppercase tracking-wide opacity-80">
                <BookOpen className="w-4 h-4" />
                <span>已加载SKILLS</span>
            </div>
            <div className="flex flex-wrap gap-2">
                {skills.map((skill) => (
                    <div
                        key={skill.path}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-white rounded-lg text-violet-700 text-xs font-medium border border-violet-100 shadow-sm"
                        title={skill.description}
                    >
                        <Sparkles className="w-3 h-3 text-violet-500" />
                        {formatSkillName(skill.skill)}
                    </div>
                ))}
            </div>
        </div>
    );
}

/**
 * 单个内联工具调用 - 可折叠
 */
function InlineToolCall({ toolCall }: { toolCall: ToolCall }) {
    const [isOpen, setIsOpen] = useState(false);

    return (
        <div className="my-2">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="inline-flex items-center gap-2 text-xs text-slate-500 hover:text-indigo-600 cursor-pointer transition-colors select-none py-1 px-2 rounded-lg hover:bg-slate-50 border border-transparent hover:border-slate-200"
            >
                <div className="w-5 h-5 rounded bg-slate-100 flex items-center justify-center">
                    <Play className="w-2.5 h-2.5" />
                </div>
                <span className="font-mono font-medium">{toolCall.name}</span>
                <ChevronRight className={cn("w-3 h-3 transition-transform", isOpen && "rotate-90")} />
            </button>

            {isOpen && (
                <div className="mt-2 ml-1 text-xs bg-slate-50 rounded-lg border border-slate-100 overflow-hidden">
                    <div className="bg-slate-100/50 px-3 py-1.5 border-b border-slate-100 font-mono text-slate-600 font-medium flex justify-between">
                        <span>{toolCall.name}</span>
                        <span className="opacity-50 text-[10px]">ARGS</span>
                    </div>
                    <div className="p-3 font-mono text-slate-500 whitespace-pre-wrap leading-relaxed">
                        {JSON.stringify(toolCall.args, null, 2)}
                    </div>
                    {toolCall.result && (
                        <div className="px-3 py-2 border-t border-slate-100 bg-emerald-50/30 text-emerald-700/80 italic break-all">
                            → {toolCall.truncated ? toolCall.result.slice(0, 150) + "..." : toolCall.result}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

/**
 * 旧版工具调用视图 - 所有工具折叠在一起 (备用)
 */
function ToolCallsView({ toolCalls }: { toolCalls: ToolCall[] }) {
    if (!toolCalls || toolCalls.length === 0) return null;

    return (
        <details className="mb-4 group/tools">
            <summary className="inline-flex items-center gap-2 text-xs text-slate-400 hover:text-indigo-600 cursor-pointer transition-colors select-none py-1">
                <div className="w-5 h-5 rounded bg-slate-100 flex items-center justify-center group-hover/tools:bg-indigo-50">
                    <Play className="w-2.5 h-2.5" />
                </div>
                <span>执行了 {toolCalls.length} 个工具</span>
            </summary>
            <div className="mt-3 space-y-3 pl-1">
                {toolCalls.map((tool, ti) => (
                    <div key={ti} className="text-xs bg-slate-50 rounded-lg border border-slate-100 overflow-hidden">
                        <div className="bg-slate-100/50 px-3 py-1.5 border-b border-slate-100 font-mono text-slate-600 font-medium flex justify-between">
                            <span>{tool.name}</span>
                            <span className="opacity-50 text-[10px]">ARGS</span>
                        </div>
                        <div className="p-3 font-mono text-slate-500 whitespace-pre-wrap leading-relaxed">
                            {JSON.stringify(tool.args, null, 2)}
                        </div>
                        {tool.result && (
                            <div className="px-3 py-2 border-t border-slate-100 bg-emerald-50/30 text-emerald-700/80 italic break-all">
                                → {tool.truncated ? tool.result.slice(0, 150) + "..." : tool.result}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </details>
    );
}

/**
 * 按顺序渲染内容片段 (文本 + 工具调用交织)
 */
function SegmentedContent({ segments }: { segments: ContentSegment[] }) {
    if (!segments || segments.length === 0) return null;

    return (
        <>
            {segments.map((segment, idx) => {
                if (segment.type === "text") {
                    return segment.content ? (
                        <MarkdownText key={idx}>{segment.content}</MarkdownText>
                    ) : null;
                } else {
                    return <InlineToolCall key={idx} toolCall={segment.toolCall} />;
                }
            })}
        </>
    );
}

function AssistantMessageBubble({ message, agentId }: { message: ChatMessage; agentId: string }) {
    const colors = getAgentColor(agentId);
    const AgentIcon = getAgentIcon(agentId);

    // 使用 segments 进行内联渲染，如果没有 segments 则回退到旧逻辑
    const hasSegments = message.segments && message.segments.length > 0;

    return (
        <div className="flex flex-col gap-2 max-w-3xl w-full">
            {/* Avatar */}
            <div className="flex items-center gap-3 px-1">
                <div className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center border shadow-sm",
                    colors.bg.replace("600", "100"),
                    colors.text
                )}>
                    <AgentIcon className="w-4 h-4" />
                </div>
            </div>

            {/* Content */}
            <div className="p-5 rounded-2xl text-[15px] leading-relaxed relative overflow-hidden shadow-sm bg-white text-slate-800 mr-12 rounded-tl-sm border border-slate-100">
                {/* Todos */}
                {message.todos && <TodoListView todos={message.todos} />}

                {/* Skills (在任务计划下面) */}
                {message.skills && <SkillsView skills={message.skills} />}

                {/* 使用 segments 内联渲染 (优先) */}
                {hasSegments ? (
                    <SegmentedContent segments={message.segments!} />
                ) : (
                    <>
                        {/* 旧版：Tool Calls 集中显示 */}
                        {message.toolCalls && <ToolCallsView toolCalls={message.toolCalls} />}

                        {/* Markdown Content */}
                        {message.content ? (
                            <MarkdownText>{message.content}</MarkdownText>
                        ) : message.isStreaming ? (
                            <div className="flex items-center gap-2 text-slate-400 text-sm h-6 pl-1">
                                <LoaderCircle className="w-4 h-4 animate-spin" />
                                思考中...
                            </div>
                        ) : null}
                    </>
                )}

                {/* Streaming indicator when using segments */}
                {hasSegments && message.isStreaming && !message.content && (
                    <div className="flex items-center gap-2 text-slate-400 text-sm h-6 pl-1 mt-2">
                        <LoaderCircle className="w-4 h-4 animate-spin" />
                        思考中...
                    </div>
                )}

                {/* Error */}
                {message.error && (
                    <div className="mt-3 p-3 bg-red-50 text-red-600 text-sm rounded-lg border border-red-100 flex items-center gap-2">
                        <Shield className="w-4 h-4" />
                        {message.error}
                    </div>
                )}
            </div>
        </div>
    );
}

function MessageLoading() {
    return (
        <div className="flex items-start mr-auto gap-2">
            <div className="flex items-center gap-1 rounded-2xl bg-muted px-4 py-2 h-8">
                <div className="w-1.5 h-1.5 rounded-full bg-foreground/50 animate-[pulse_1.5s_ease-in-out_infinite]" />
                <div className="w-1.5 h-1.5 rounded-full bg-foreground/50 animate-[pulse_1.5s_ease-in-out_0.5s_infinite]" />
                <div className="w-1.5 h-1.5 rounded-full bg-foreground/50 animate-[pulse_1.5s_ease-in-out_1s_infinite]" />
            </div>
        </div>
    );
}

// ============================================================
// 主组件
// ============================================================

export function FastAPIThread() {
    const stream = useFastAPIStream();
    const { messages, isLoading, currentAgent, agents, submit, clearMessages, setCurrentAgent, newSession } = stream;

    const [input, setInput] = useState("");
    const [agentDropdownOpen, setAgentDropdownOpen] = useState(false);
    const inputRef = useRef<HTMLTextAreaElement>(null);

    const handleSubmit = (e: FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;
        submit(input);
        setInput("");
    };

    const chatStarted = messages.length > 0;
    const colors = currentAgent ? getAgentColor(currentAgent.id) : { bg: "bg-slate-600", text: "text-slate-600" };
    const AgentIcon = currentAgent ? getAgentIcon(currentAgent.id) : Bot;

    // 点击外部关闭下拉
    useEffect(() => {
        const handler = (e: MouseEvent) => {
            const target = e.target as HTMLElement;
            if (!target.closest(".agent-dropdown")) {
                setAgentDropdownOpen(false);
            }
        };
        document.addEventListener("click", handler);
        return () => document.removeEventListener("click", handler);
    }, []);

    return (
        <div className="flex w-full h-screen overflow-hidden bg-slate-50">
            <Sidebar />
            <div className="flex-1 flex flex-col h-screen overflow-hidden bg-white shadow-xl rounded-l-2xl border-l border-slate-100/50">
                {/* Header */}
                <header className="bg-white border-b px-4 py-3 flex items-center justify-between sticky top-0 z-10">
                    <div className="flex items-center gap-3">
                        {currentAgent && (
                            <>
                                <div className={cn(colors.bg, "w-9 h-9 rounded-xl flex items-center justify-center text-white shadow-md")}>
                                    <AgentIcon className="w-5 h-5" />
                                </div>
                                <div>
                                    <h1 className="font-bold text-base leading-tight">{currentAgent.name}</h1>
                                    <p className="text-[10px] text-slate-500 font-medium tracking-wide uppercase">
                                        v{currentAgent.version}
                                    </p>
                                </div>
                            </>
                        )}
                    </div>

                    <div className="flex items-center gap-2">
                        {/* Agent Selector */}
                        {agents.length > 1 && (
                            <div className="relative agent-dropdown">
                                <button
                                    onClick={() => setAgentDropdownOpen(!agentDropdownOpen)}
                                    className="flex items-center gap-2 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors text-xs font-medium text-slate-700 border border-slate-200"
                                >
                                    <AgentIcon className="w-3.5 h-3.5" />
                                    <span className="max-w-[100px] truncate">{currentAgent?.name}</span>
                                    <ChevronDown className={cn("w-3.5 h-3.5 transition-transform", agentDropdownOpen && "rotate-180")} />
                                </button>

                                {agentDropdownOpen && (
                                    <div className="absolute right-0 top-full mt-2 w-64 bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden z-50">
                                        <div className="p-1.5">
                                            {agents.map((agent) => (
                                                <button
                                                    key={agent.id}
                                                    onClick={() => {
                                                        setCurrentAgent(agent);
                                                        setAgentDropdownOpen(false);
                                                    }}
                                                    className={cn(
                                                        "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-left",
                                                        currentAgent?.id === agent.id ? "bg-slate-50" : "hover:bg-slate-50"
                                                    )}
                                                >
                                                    <div className={cn(getAgentColor(agent.id).bg, "w-7 h-7 rounded-lg flex items-center justify-center text-white shrink-0")}>
                                                        {React.createElement(getAgentIcon(agent.id), { className: "w-3.5 h-3.5" })}
                                                    </div>
                                                    <div className="min-w-0">
                                                        <div className="font-medium text-xs text-slate-800">{agent.name}</div>
                                                        <div className="text-[10px] text-slate-400 truncate">{agent.description}</div>
                                                    </div>
                                                    {currentAgent?.id === agent.id && (
                                                        <CheckCircle2 className="w-4 h-4 text-indigo-600 ml-auto" />
                                                    )}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* New Chat */}
                        <Button variant="ghost" size="sm" onClick={() => newSession()}>
                            <SquarePen className="w-4 h-4" />
                        </Button>
                    </div>
                </header>

                {/* Chat Area */}
                <StickToBottom className="relative flex-1 overflow-hidden">
                    <StickyToBottomContent
                        className={cn(
                            "absolute px-4 inset-0 overflow-y-scroll [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-track]:bg-transparent",
                            !chatStarted && "flex flex-col items-stretch mt-[25vh]"
                        )}
                        contentClassName="pt-8 pb-16 max-w-3xl mx-auto flex flex-col gap-4 w-full"
                        content={
                            <>
                                {!chatStarted && currentAgent && (
                                    <div className="flex flex-col items-center justify-center text-slate-400 opacity-80 min-h-[200px]">
                                        <AgentIcon className="w-16 h-16 mb-6 text-slate-200" />
                                        <h2 className="text-xl font-semibold text-slate-700 mb-2">有什么可以帮你的？</h2>
                                        <p className="text-sm text-slate-500 max-w-xs text-center leading-relaxed">
                                            我是 {currentAgent.name}。
                                            <br />
                                            {currentAgent.description}
                                        </p>
                                    </div>
                                )}

                                {messages.map((msg) =>
                                    msg.type === "human" ? (
                                        <HumanMessageBubble key={msg.id} message={msg} />
                                    ) : (
                                        <AssistantMessageBubble key={msg.id} message={msg} agentId={currentAgent?.id || "default"} />
                                    )
                                )}

                                {isLoading && messages.length > 0 && !messages[messages.length - 1]?.isStreaming && (
                                    <MessageLoading />
                                )}
                            </>
                        }
                        footer={
                            <div className="sticky flex flex-col items-center gap-8 bottom-0 bg-white">
                                <ScrollToBottom className="absolute bottom-full left-1/2 -translate-x-1/2 mb-4 animate-in fade-in-0 zoom-in-95" />

                                <div className="bg-muted rounded-2xl border shadow-xs mx-auto mb-8 w-full max-w-3xl relative z-10">
                                    <form onSubmit={handleSubmit} className="grid grid-rows-[1fr_auto] gap-2 max-w-3xl mx-auto">
                                        <textarea
                                            ref={inputRef}
                                            value={input}
                                            onChange={(e) => setInput(e.target.value)}
                                            onKeyDown={(e) => {
                                                if (e.key === "Enter" && !e.shiftKey && !e.metaKey && !e.nativeEvent.isComposing) {
                                                    e.preventDefault();
                                                    handleSubmit(e);
                                                }
                                            }}
                                            placeholder="粘贴告警 JSON 或描述问题..."
                                            className="p-3.5 pb-0 border-none bg-transparent field-sizing-content shadow-none ring-0 outline-none focus:outline-none focus:ring-0 resize-none"
                                        />

                                        <div className="flex items-center justify-end p-2 pt-4">
                                            {isLoading ? (
                                                <Button onClick={() => stream.stop()}>
                                                    <LoaderCircle className="w-4 h-4 animate-spin" />
                                                    取消
                                                </Button>
                                            ) : (
                                                <Button type="submit" disabled={!input.trim()}>
                                                    发送
                                                </Button>
                                            )}
                                        </div>
                                    </form>
                                </div>
                            </div>
                        }
                    />
                </StickToBottom>
            </div>
        </div>
    );
}

import React from "react";
