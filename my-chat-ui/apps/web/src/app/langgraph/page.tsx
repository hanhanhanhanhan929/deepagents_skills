"use client";

import { Thread } from "@/components/thread";
import { StreamProvider } from "@/providers/Stream";
import { ThreadProvider } from "@/providers/Thread";
import { Toaster } from "@/components/ui/sonner";
import React from "react";

/**
 * LangGraph 原版页面
 * 
 * 保留原有的 LangGraph Server 集成
 */
export default function LangGraphPage(): React.ReactNode {
    return (
        <React.Suspense fallback={<div>Loading (layout)...</div>}>
            <Toaster />
            <ThreadProvider>
                <StreamProvider>
                    <Thread />
                </StreamProvider>
            </ThreadProvider>
        </React.Suspense>
    );
}
