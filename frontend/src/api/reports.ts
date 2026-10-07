import { apiRequest } from "./client";

export type AgingSortBy =
  | "total"
  | "current"
  | "days_1_30"
  | "days_31_60"
  | "days_61_90"
  | "days_90_plus";

export interface VendorAging {
  vendor_id: string;
  current_cents: number;
  days_1_30_cents: number;
  days_31_60_cents: number;
  days_61_90_cents: number;
  days_90_plus_cents: number;
  total_outstanding_cents: number;
  vendor_rank: number;
  share_pct: number;
}

export interface AgingReport {
  as_of: string;
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
  vendors: VendorAging[];
}

export function getAgingReport(
  asOf: string,
  page: number,
  pageSize: number,
  sortBy: AgingSortBy,
  sortOrder: "asc" | "desc",
  vendorId?: string,
): Promise<AgingReport> {
  const params = new URLSearchParams({
    as_of: asOf,
    page: String(page),
    page_size: String(pageSize),
    sort_by: sortBy,
    sort_order: sortOrder,
  });

  if (vendorId) {
    params.set("vendor_id", vendorId);
  }

  return apiRequest<AgingReport>(`/reports/aging?${params.toString()}`);
}