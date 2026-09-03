"use client";

import { PropertyGrid } from "@/features/properties/property-grid";

export default function PropertiesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Properties</h1>
        <p className="text-sm text-muted-foreground">
          Your organization&apos;s catalogue — the pool the AI matches leads against.
        </p>
      </div>
      <PropertyGrid />
    </div>
  );
}
