import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind class names (required by shadcn/ui components). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
