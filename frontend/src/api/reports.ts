import { apiRequest } from "./client";

export interface AgingBucketSummary {
  invoice_count: number;
  amount_cents: number;
}

export interface AgingInvoice {
  invoice_id: string;
  vendor_id: string;
  invoice_number: string;
  due_date: string;
  outstanding_cents: number;
  days_past_due: number;
  bucket: string;
}

export interface AgingReport {
  as_of: string;
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
  buckets: Record<string, AgingBucketSummary>;
  invoices: AgingInvoice[];
}

export function getAgingReport(
  asOf: string,
  page: number,
  pageSize: number,
  bucketOrder: "asc" | "desc",
  vendorId?: string,
): Promise<AgingReport> {
  const params = new URLSearchParams({
    as_of: asOf,
    page: String(page),
    page_size: String(pageSize),
    bucket_order: bucketOrder,
  });
if (vendorId) params.set("vendor_id", vendorId);
  return apiRequest<AgingReport>(`/reports/aging?${params.toString()}`);
}