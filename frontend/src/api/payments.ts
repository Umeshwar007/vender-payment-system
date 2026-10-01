import { apiRequest } from "./client";

export interface Payment {
  id: string;
  invoice_id: string;
  amount_cents: number;
  status: string;
  bank_reference: string | null;
}

export interface PaymentRun {
  id: string;
  status: string;
  total_cents: number;
  created_at: string;
  completed_at: string | null;
  payments: Payment[];
}

export function createPaymentRun(invoiceIds: string[]): Promise<PaymentRun> {
  return apiRequest<PaymentRun>("/payment-runs", {
    method: "POST",
    body: JSON.stringify({ invoice_ids: invoiceIds }),
  });
}

export function executePaymentRun(runId: string): Promise<PaymentRun> {
  return apiRequest<PaymentRun>(`/payment-runs/${runId}/execute`, {
    method: "POST",
  });
}

export function reconcilePaymentRun(runId: string): Promise<PaymentRun> {
  return apiRequest<PaymentRun>(`/payment-runs/${runId}/reconcile`, {
    method: "POST",
  });
}