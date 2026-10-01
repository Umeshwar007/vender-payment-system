import { apiRequest } from "./client";

export type InvoiceStatus =
  | "draft"
  | "approved"
  | "scheduled"
  | "partially_paid"
  | "paid"
  | "void";

export interface InvoiceSummary {
  id: string;
  vendor_id: string;
  invoice_number: string;
  status: InvoiceStatus;
  issued_date: string;
  due_date: string;
  total_cents: number;
  amount_paid_cents: number;
  created_at: string;
}

export interface InvoicePage {
  items: InvoiceSummary[];
  total: number;
  limit: number;
  offset: number;
}

export function getInvoices(
  limit: number,
  offset: number,
): Promise<InvoicePage> {
  return apiRequest<InvoicePage>(
    `/invoices?limit=${limit}&offset=${offset}`,
  );
}