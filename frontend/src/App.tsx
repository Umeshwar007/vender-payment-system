import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
const [editingInvoiceId, setEditingInvoiceId] = useState<string | null>(null);
import { getInvoices, type InvoiceStatus, deleteInvoice } from "./api/invoices";
import "./App.css";
import InvoiceForm from "./components/InvoiceForm";
import { updateInvoiceStatus } from "./api/invoices";
const PAGE_SIZE = 20;
import AgingReportPanel from "./components/AgingReportPanel";
import PaymentRunsPanel from "./components/PaymentRunsPanel";
function money(cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(cents / 100);
}

function shortId(id: string): string {
  return `${id.slice(0, 8)}…`;
}

const statusLabels: Record<InvoiceStatus, string> = {
  draft: "Draft",
  approved: "Approved",
  scheduled: "Scheduled",
  partially_paid: "Partially paid",
  paid: "Paid",
  void: "Void",
};

export default function App() {
  const [offset, setOffset] = useState(0);

  const invoicesQuery = useQuery({
    queryKey: ["invoices", offset],
    queryFn: () => getInvoices(PAGE_SIZE, offset),
  });
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [activeView, setActiveView] = useState<
    "invoices" | "payments" | "aging"
  >("invoices");

  const queryClient = useQueryClient();

  const statusMutation = useMutation({
    mutationFn: ({
      invoiceId,
      status,
    }: {
      invoiceId: string;
      status: InvoiceStatus;
    }) => updateInvoiceStatus(invoiceId, status),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["invoices"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteInvoice,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["invoices"] }),
  });
  const page = invoicesQuery.data;
  const start = page && page.total > 0 ? page.offset + 1 : 0;
  const end = page ? Math.min(page.offset + page.items.length, page.total) : 0;

  return (
    <main className="app-shell">
      <header className="page-header">
        <div>
          <p className="eyebrow">PAYABLES WORKSPACE</p>
          <h1>
            {activeView === "invoices"
              ? "Invoices"
              : activeView === "payments"
                ? "Payment runs"
                : "Aging report"}
          </h1>
          <p className="page-subtitle">
            {activeView === "invoices"
              ? "Review vendor invoices and track their payment status."
              : activeView === "payments"
                ? "Prepare and execute payments for scheduled invoices."
                : "Review outstanding balances by aging bucket."}
          </p>

        </div>
        <div className="header-actions">
          <button
            className="primary-button"
            type="button"
            onClick={() => setShowCreateForm(true)}
          >
            New invoice
          </button>
          <div className="header-mark" aria-hidden="true">AP</div>
        </div>
      </header>
      {(showCreateForm || editingInvoiceId !== null) && (
        <InvoiceForm
          invoiceId={editingInvoiceId ?? undefined}
          onClose={() => {
            setShowCreateForm(false);
            setEditingInvoiceId(null);
          }}
          onCreated={() => {
            setOffset(0);
            setShowCreateForm(false);
            setEditingInvoiceId(null);
          }}
        />
      )}
      {deleteMutation.isError && (
        <div className="notice notice-error" role="alert">
          Couldn’t delete invoice: {deleteMutation.error?.message}
        </div>
      )}
      <nav className="view-tabs" aria-label="Accounts payable views">
        <button
          type="button"
          className={activeView === "invoices" ? "view-tab active" : "view-tab"}
          aria-pressed={activeView === "invoices"}
          onClick={() => setActiveView("invoices")}
        >
          Invoices
        </button>
        <button
          type="button"
          className={activeView === "payments" ? "view-tab active" : "view-tab"}
          aria-pressed={activeView === "payments"}
          onClick={() => setActiveView("payments")}
        >
          Payment runs
        </button>
        <button
          type="button"
          className={activeView === "aging" ? "view-tab active" : "view-tab"}
          aria-pressed={activeView === "aging"}
          onClick={() => setActiveView("aging")}
        >
          Aging report
        </button>
      </nav>

      {activeView === "payments" && <PaymentRunsPanel />}
      {activeView === "aging" && <AgingReportPanel />}
      {activeView === "invoices" && (
        <section className="content-card" aria-labelledby="invoice-list-heading">
          <div className="card-heading">
            <div>
              <h2 id="invoice-list-heading">Invoice register</h2>
              <p>
                {page
                  ? `${start}–${end} of ${page.total} invoices`
                  : "Invoices from your workspace"}
              </p>
            </div>
            <span className="count-pill">
              {page ? `${page.total} total` : "Loading"}
            </span>
          </div>

          {invoicesQuery.isPending && (
            <div className="notice" role="status">Loading invoices…</div>
          )}

          {invoicesQuery.isError && (
            <div className="notice notice-error" role="alert">
              Couldn’t load invoices: {invoicesQuery.error.message}
            </div>
          )}

          {page && page.items.length === 0 && (
            <div className="empty-state">
              <h3>No invoices yet</h3>
              <p>Invoices will appear here when they’re added to the system.</p>
            </div>
          )}

          {page && page.items.length > 0 && (
            <>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Invoice</th>
                      <th>Vendor ID</th>
                      <th>Status</th>
                      <th>Issued</th>
                      <th>Due date</th>
                      <th className="numeric">Amount</th>
                      <th className="numeric">Paid</th>
                      <th className="numeric">Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {page.items.map((invoice) => (
                      <tr key={invoice.id}>
                        <td>
                          <strong>{invoice.invoice_number}</strong>
                          <span className="secondary-cell">
                            {shortId(invoice.id)}
                          </span>
                        </td>
                        <td className="muted-cell">{shortId(invoice.vendor_id)}</td>
                        <td>
                          <span className={`status-badge status-${invoice.status}`}>
                            {(invoice.status === "draft" || invoice.status === "approved") && (
                              <button
                                type="button"
                                disabled={statusMutation.isPending}
                                onClick={() =>
                                  statusMutation.mutate({
                                    invoiceId: invoice.id,
                                    status: invoice.status === "draft" ? "approved" : "scheduled",
                                  })
                                }
                              >
                                {invoice.status === "draft" ? "Approve" : "Schedule"}
                              </button>
                            )}
                            {invoice.status === "draft" && (
                              <button
                                type="button"
                                onClick={() => setEditingInvoiceId(invoice.id)}
                              >
                                Edit
                              </button>
                            )}
                            {invoice.status === "draft" && (
                              <button
                                type="button"
                                disabled={deleteMutation.isPending}
                                onClick={() => {
                                  if (window.confirm(`Delete draft invoice ${invoice.invoice_number}?`)) {
                                    deleteMutation.mutate(invoice.id);
                                  }
                                }}
                              >
                                Delete
                              </button>
                            )}
                            <span className="status-dot" />
                            {statusLabels[invoice.status]}
                          </span>
                        </td>
                        <td>{invoice.issued_date}</td>
                        <td>{invoice.due_date}</td>
                        <td className="numeric">{money(invoice.total_cents)}</td>
                        <td className="numeric">{money(invoice.amount_paid_cents)}</td>
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
        </section>
      )}
    </main>
  );
}