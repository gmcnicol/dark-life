import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

function padDatePart(value: number): string {
  return String(value).padStart(2, "0");
}

export function parseDateValue(value?: string | number | Date | null): Date | null {
  if (value == null) {
    return null;
  }
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatLocalDateTime(value?: string | number | Date | null, fallback = "Unknown"): string {
  const date = parseDateValue(value);
  if (!date) {
    return fallback;
  }
  const day = padDatePart(date.getDate());
  const month = padDatePart(date.getMonth() + 1);
  const year = date.getFullYear();
  const hours = padDatePart(date.getHours());
  const minutes = padDatePart(date.getMinutes());
  return `${day}-${month}-${year} ${hours}:${minutes}`;
}

export function formatLocalTime(value?: string | number | Date | null, fallback = "Unknown"): string {
  const date = parseDateValue(value);
  if (!date) {
    return fallback;
  }
  const hours = padDatePart(date.getHours());
  const minutes = padDatePart(date.getMinutes());
  return `${hours}:${minutes}`;
}

export function isSameLocalDay(value?: string | number | Date | null, now = new Date()): boolean {
  const date = parseDateValue(value);
  if (!date) {
    return false;
  }
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  );
}
