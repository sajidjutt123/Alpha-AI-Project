"use client";

/** Organization catalogue browser. */

import { useCallback, useEffect, useState } from "react";

import { propertiesApi } from "@/lib/api";
import type { Property, PropertyType } from "@/types/api";
import { formatPkr } from "@/components/dash/ui";

const TYPES: PropertyType[] = ["HOUSE", "APARTMENT", "PLOT", "COMMERCIAL"];

const AVAILABILITY_STYLES: Record<Property["availability"], string> = {
  AVAILABLE: "border-primary/40 bg-primary/10 text-primary",
  RESERVED: "border-accent/40 bg-accent/10 text-accent",
  SOLD: "border-destructive/40 bg-destructive/10 text-destructive",
  RENTED: "border-border bg-muted text-muted-foreground",
};

export function PropertyGrid() {
  const [items, setItems] = useState<Property[] | null>(null);
  const [type, setType] = useState("");
  const [location, setLocation] = useState("");
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    try {
      const page = await propertiesApi.list({
        property_type: type || undefined,
        location: location || undefined,
        limit: 60,
      });
      setItems(page.items);
      setError(false);
    } catch {
      setError(true);
    }
  }, [type, location]);

  useEffect(() => {
    const timer = setTimeout(() => void load(), location ? 300 : 0);
    return () => clearTimeout(timer);
  }, [load, location]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <input
          value={location}
          onChange={(event) => setLocation(event.target.value)}
          placeholder="Location (e.g. DHA, Gulberg, Clifton)…"
          className="min-w-56 flex-1 rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none focus:border-primary"
        />
        <select
          value={type}
          onChange={(event) => setType(event.target.value)}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none focus:border-primary"
        >
          <option value="">All types</option>
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <p className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          Failed to load properties.
        </p>
      )}
      {!error && items === null && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-40 animate-pulse rounded-xl bg-card" />
          ))}
        </div>
      )}

      {items && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((prop) => (
            <div key={prop.id} className="space-y-3 rounded-xl border border-border bg-card p-5">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-semibold">{prop.title}</p>
                <span
                  className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${AVAILABILITY_STYLES[prop.availability]}`}
                >
                  {prop.availability}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">{prop.location}</p>
              <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                <span className="rounded-full border border-border px-2 py-0.5 font-medium text-foreground">
                  {formatPkr(prop.price)}
                </span>
                <span className="rounded-full border border-border px-2 py-0.5">
                  {prop.property_type}
                </span>
                {prop.bedrooms != null && (
                  <span className="rounded-full border border-border px-2 py-0.5">
                    {prop.bedrooms} bed
                  </span>
                )}
                {prop.area != null && (
                  <span className="rounded-full border border-border px-2 py-0.5">
                    {prop.area.toLocaleString()} sqft
                  </span>
                )}
              </div>
              {prop.description && (
                <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                  {prop.description}
                </p>
              )}
            </div>
          ))}
          {items.length === 0 && (
            <p className="col-span-full rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
              No properties match these filters.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
