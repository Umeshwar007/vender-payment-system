import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { getInvoices } from "../api/invoices";
import {
  createPaymentRun,
  executePaymentRun,
  reconcilePaymentRun,
  type PaymentRun,
} from "../api/payments";

const PAGE_SIZE = 20;

function money(cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(cents / 100);
}

export default function PaymentRunsPanel() {
 
  const [offset, setOffset] = useState(0);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [run, setRun] = useState<PaymentRun | null>(null);

  const invoicesQuery = useQuery({
    queryKey: ["invoices", "scheduled", offset],
    queryFn: () => getInvoices(PAGE_SIZE, offset, "scheduled"),
  });

  const createMutation = useMutation({
    mutationFn: createPaymentRun,
    onSuccess: (createdRun) => {
      setRun(createdRun);
      setSelectedIds([]);
    },
  });

  const executeMutation = useMutation({
    mutationFn: executePaymentRun,
    onSuccess: setRun,
  });

  const reconcileMutation = useMutation({
    mutationFn: reconcilePaymentRun,
    onSuccess: setRun,
  });

  const page = invoicesQuery.data;
  const start = page && page.total > 0 ? page.offset + 1 : 0;
  const end = page ? Math.min(page.offset + page.items.length, page.total) : 0;
  const actionError =
    createMutation.error?.message ??
    executeMutation.error?.message ??
    reconcileMutation.error?.message;

  function toggleInvoice(invoiceId: string) {
    setSelectedIds((current) =>
      current.includes(invoiceId)
        ? current.filter((id) => id !== invoiceId)
        : [...current, invoiceId],
    );
  }

  return (
    <section className="content-card" aria-labelledby="payment-runs-heading">
      <div className="card-heading">
        <div>
          <h2 id="payment-runs-heading">Create a payment run</h2>
          <p>Select scheduled invoices to prepare for payment.</p>
        </div>
        <span className="count-pill">
          {selectedIds.length} selected
        </span>
      </div>

      {invoicesQuery.isPending && (
        <div className="notice" role="status">Loading scheduled invoices…</div>
      )}

      {invoicesQuery.isError && (
        <div className="notice notice-error" role="alert">
          Couldn’t load invoices: {invoicesQuery.error.message}
        </div>
      )}

      {page && page.items.length === 0 && (
        <div className="empty-state">
          <h3>No scheduled invoices</h3>
          <p>Invoices must be scheduled before they can be added to a run.</p>
        </div>
      )}

      {page && page.items.length > 0 && (
        <>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th><span className="visually-hidden">Select</span></th>
                  <th>Invoice</th>
                  <th>Vendor ID</th>
                  <th>Due date</th>
                  <th className="numeric">Outstanding</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((invoice) => (
                  <tr key={invoice.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(invoice.id)}
                        onChange={() => toggleInvoice(invoice.id)}
                        aria-label={`Select invoice ${invoice.invoice_number}`}
                      />
                    </td>
                    <td><strong>{invoice.invoice_number}</strong></td>
                    <td className="muted-cell">{invoice.vendor_id.slice(0, 8)}…</td>
                    <td>{invoice.due_date}</td>
                    <td className="numeric balance-cell">
                      {money(invoice.total_cents - invoice.amount_paid_cents)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <footer className="pagination">
            <span>Showing {start}–{end} of {page.total}</span>
            <div>
              <button
                type="button"
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                disabled={offset === 0 || invoicesQuery.isFetching}
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setOffset(offset + PAGE_SIZE)}
                disabled={end >= page.total || invoicesQuery.isFetching}
              >
                Next
              </button>
            </div>
          </footer>
        </>
      )}

      <div className="run-actions">
        <button
          className="primary-button"
          type="button"
          disabled={selectedIds.length === 0 || createMutation.isPending}
          onClick={() => createMutation.mutate(selectedIds)}
        >
          {createMutation.isPending ? "Creating…" : "Create payment run"}
        </button>
      </div>

      {actionError && (
        <div className="notice notice-error" role="alert">{actionError}</div>
      )}

      {run && (
        <section className="run-result" aria-labelledby="run-result-heading">
          <div className="card-heading">
            <div>
              <h2 id="run-result-heading">Payment run</h2>
              <p className="run-id">{run.id}</p>
            </div>
            <span className="count-pill">{run.status.replaceAll("_", " ")}</span>
          </div>

          <div className="run-total">
            <span>Total</span>
            <strong>{money(run.total_cents)}</strong>
          </div>

          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Invoice ID</th>
                  <th>Status</th>
                  <th className="numeric">Amount</th>
                  <th>Bank reference</th>
                </tr>
              </thead>
              <tbody>
                {run.payments.map((payment) => (
                  <tr key={payment.id}>
                    <td className="muted-cell">{payment.invoice_id}</td>
                    <td>{payment.status.replaceAll("_", " ")}</td>
                    <td className="numeric">{money(payment.amount_cents)}</td>
                    <td className="muted-cell">
                      {payment.bank_reference ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="run-actions">
            {run.status === "created" && (
              <button
                className="primary-button"
                type="button"
                disabled={executeMutation.isPending}
                onClick={() => executeMutation.mutate(run.id)}
              >
                {executeMutation.isPending ? "Executing…" : "Execute run"}
              </button>
            )}

            {run.status === "needs_reconciliation" && (
              <button
                className="primary-button"
                type="button"
                disabled={reconcileMutation.isPending}
                onClick={() => reconcileMutation.mutate(run.id)}
              >
                {reconcileMutation.isPending ? "Checking bank…" : "Reconcile"}
              </button>
            )}
          </div>
        </section>
      )}
    </section>
  );
}