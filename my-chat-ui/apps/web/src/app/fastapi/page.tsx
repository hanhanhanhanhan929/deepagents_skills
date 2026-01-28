"use client";

import { FastAPIThread } from "@/components/thread/fastapi-thread";
import { FastAPIStreamProvider } from "@/providers/FastAPIStream";
import { Toaster } from "@/components/ui/sonner";
import React from "react";

export default function FastAPIPage(): React.ReactNode {
    return (
        <React.Suspense fallback={<div className="flex items-center justify-center h-screen">Loading...</div>}>
            <Toaster />
            <FastAPIStreamProvider>
                <FastAPIThread />
            </FastAPIStreamProvider>
        </React.Suspense>
    );
}
