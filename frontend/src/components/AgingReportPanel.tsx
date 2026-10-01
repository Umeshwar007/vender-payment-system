import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getAgingReport } from "../api/reports";

const PAGE_SIZE = 20;
const BUCKETS = [
  ["current", "Current"],
  ["1-30", "1–30 days"],
  ["31-60", "31–60 days"],
  ["61-90", "61–90 days"],
  ["over-90", "Over 90 days"],
] as const;

function localDate(): string {
  const today = new Date();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  return `${today.getFullYear()}-${month}-${day}`;
}

function money(cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(cents / 100);
}

export default function AgingReportPanel() {
  const [asOf, setAsOf] = useState(localDate);
  const [page, setPage] = useState(1);
  const [bucketOrder, setBucketOrder] = useState<"asc" | "desc">("asc");

  const reportQuery = useQuery({
    queryKey: ["aging-report", asOf, page, bucketOrder],
    queryFn: () => getAgingReport(asOf, page, PAGE_SIZE, bucketOrder),
  });

  const report = reportQuery.data;

  return (
    <section className="content-card" aria-labelledby="aging-heading">
      <div className="card-heading aging-heading">
        <div>
          <h2 id="aging-heading">Accounts payable aging</h2>
          <p>Outstanding invoice balances grouped by days past due.</p>
        </div>

        <div className="aging-controls">
          <label>
            <span>As of</span>
            <input
              type="date"
              value={asOf}
              onChange={(event) => {
                setAsOf(event.target.value);
                setPage(1);
              }}
            />
          </label>
          <label>
            <span>Bucket order</span>
            <select
              value={bucketOrder}
              onChange={(event) => {
                setBucketOrder(event.target.value as "asc" | "desc");
                setPage(1);
              }}
            >
              <option value="asc">Current to oldest</option>
              <option value="desc">Oldest to current</option>
            </select>
          </label>
        </div>
      </div>

      {reportQuery.isPending && (
        <div className="notice" role="status">Loading aging report…</div>
      )}

      {reportQuery.isError && (
        <div className="notice notice-error" role="alert">
          Couldn’t load the report: {reportQuery.error.message}
        </div>
      )}

      {report && (
        <>
          <div className="aging-summary">
            {BUCKETS.map(([key, label]) => {
              const bucket = report.buckets[key];

              return (
                <article className="aging-tile" key={key}>
                  <span>{label}</span>
                  <strong>{money(bucket.amount_cents)}</strong>
                  <small>{bucket.invoice_count} invoices</small>
                </article>
              );
            })}
          </div>

          {report.invoices.length === 0 ? (
            <div className="empty-state">
              <h3>No outstanding invoices</h3>
              <p>There are no unpaid invoice balances for this report.</p>
            </div>
          ) : (
            <>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Invoice</th>
                      <th>Bucket</th>
                      <th>Due date</th>
                      <th className="numeric">Days overdue</th>
                      <th className="numeric">Outstanding</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.invoices.map((invoice) => (
                      <tr key={invoice.invoice_id}>
                        <td>
                          <strong>{invoice.invoice_number}</strong>
                          <span className="secondary-cell">
                            {invoice.invoice_id.slice(0, 8)}…
                          </span>
                        </td>
                        <td>{invoice.bucket}</td>
                        <td>{invoice.due_date}</td>
                        <td className="numeric">{invoice.days_past_due}</td>
                        <td className="numeric balance-cell">
                          {money(invoice.outstanding_cents)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <footer className="pagination">
                <span>
                  Page {report.page} of {Math.max(report.total_pages, 1)}
                  {" · "}{report.total_count} invoices
                </span>
                <div>
                  <button
                    type="button"
                    onClick={() => setPage((current) => Math.max(1, current - 1))}
                    disabled={page <= 1 || reportQuery.isFetching}
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    onClick={() => setPage((current) => current + 1)}
                    disabled={
                      page >= report.total_pages || reportQuery.isFetching
                    }
                  >
                    Next
                  </button>
                </div>
              </footer>
            </>
          )}
        </>
      )}
    </section>
  );
}