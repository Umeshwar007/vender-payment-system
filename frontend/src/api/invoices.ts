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
  status?: InvoiceStatus,
): Promise<InvoicePage> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  if (status) params.set("status", status);

  return apiRequest<InvoicePage>(`/invoices?${params.toString()}`);
}

export interface InvoiceLineInput {
  description: string;
  quantity: number;
  unit_price_cents: number;
}

export interface InvoiceCreateInput {
  vendor_id: string;
  invoice_number: string;
  issued_date: string;
  due_date: string;
  lines: InvoiceLineInput[];
}

export function createInvoice(input: InvoiceCreateInput): Promise<unknown> {
  return apiRequest<unknown>("/invoices", {
    method: "POST",
    body: JSON.stringify(input),
  });
}


export function updateInvoiceStatus(
  invoiceId: string,
  status: InvoiceStatus,
) {
  return apiRequest(`/invoices/${invoiceId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}