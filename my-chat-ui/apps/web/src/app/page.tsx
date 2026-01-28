"use client";

import { FastAPIThread } from "@/components/thread/fastapi-thread";
import { FastAPIStreamProvider } from "@/providers/FastAPIStream";
import { Toaster } from "@/components/ui/sonner";
import React from "react";

/**
 * 主页面 - 使用 FastAPI Agent
 * 
 * 原 LangGraph 版本已移动到 /langgraph 路由
 */
export default function DemoPage(): React.ReactNode {
  return (
    <React.Suspense fallback={<div className="flex items-center justify-center h-screen">Loading...</div>}>
      <Toaster />
      <FastAPIStreamProvider>
        <FastAPIThread />
      </FastAPIStreamProvider>
    </React.Suspense>
  );
}
