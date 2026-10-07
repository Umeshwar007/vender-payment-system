import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  getAgingReport,
  type AgingSortBy,
} from "../api/reports";
import { getVendors } from "../api/vendors";

const PAGE_SIZE = 20;

const SORT_OPTIONS: Array<[AgingSortBy, string]> = [
  ["total", "Total outstanding"],
  ["current", "Current"],
  ["days_1_30", "1–30 days"],
  ["days_31_60", "31–60 days"],
  ["days_61_90", "61–90 days"],
  ["days_90_plus", "90+ days"],
];

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

function percentage(value: number): string {
  return `${value.toFixed(2)}%`;
}

export default function AgingReportPanel() {
  const [asOf, setAsOf] = useState(localDate);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<AgingSortBy>("total");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [vendorId, setVendorId] = useState("all");

  const vendorsQuery = useQuery({
    queryKey: ["vendors"],
    queryFn: getVendors,
  });

  const reportQuery = useQuery({
    queryKey: ["aging-report", asOf, page, sortBy, sortOrder, vendorId],
    queryFn: () =>
      getAgingReport(
        asOf,
        page,
        PAGE_SIZE,
        sortBy,
        sortOrder,
        vendorId === "all" ? undefined : vendorId,
      ),
  });

  const report = reportQuery.data;
  const vendorNames = new Map(
    (vendorsQuery.data?.items ?? []).map((vendor) => [
      vendor.id,
      vendor.name,
    ]),
  );

  return (
    <section className="content-card" aria-labelledby="aging-heading">
      <div className="card-heading aging-heading">
        <div>
          <h2 id="aging-heading">Accounts payable aging</h2>
          <p>
            Outstanding balances by vendor. The 90+ bucket means more than 90
            days overdue.
          </p>
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
            <span>Sort by</span>
            <select
              value={sortBy}
              onChange={(event) => {
                setSortBy(event.target.value as AgingSortBy);
                setPage(1);
              }}
            >
              {SORT_OPTIONS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Order</span>
            <select
              value={sortOrder}
              onChange={(event) => {
                setSortOrder(event.target.value as "asc" | "desc");
                setPage(1);
              }}
            >
              <option value="desc">Highest first</option>
              <option value="asc">Lowest first</option>
            </select>
          </label>

          <label>
            <span>Vendor</span>
            <select
              value={vendorId}
              onChange={(event) => {
                setVendorId(event.target.value);
                setPage(1);
              }}
            >
              <option value="all">All vendors</option>
              {(vendorsQuery.data?.items ?? []).map((vendor) => (
                <option key={vendor.id} value={vendor.id}>
                  {vendor.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {reportQuery.isPending && (
        <div className="notice" role="status">
          Loading aging report…
        </div>
      )}

      {reportQuery.isError && (
        <div className="notice notice-error" role="alert">
          Couldn’t load the report: {reportQuery.error.message}
        </div>
      )}

      {report && (
        <>
          {report.vendors.length === 0 ? (
            <div className="empty-state">
              <h3>No outstanding vendor balances</h3>
              <p>There are no unpaid invoice balances for this report.</p>
            </div>
          ) : (
            <>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Vendor</th>
                      <th className="numeric">Current</th>
                      <th className="numeric">1–30</th>
                      <th className="numeric">31–60</th>
                      <th className="numeric">61–90</th>
                      <th className="numeric">90+</th>
                      <th className="numeric">Total outstanding</th>
                      <th className="numeric">Share</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.vendors.map((vendor) => (
                      <tr key={vendor.vendor_id}>
                        <td>{vendor.vendor_rank}</td>
                        <td>
                          <strong>
                            {vendorNames.get(vendor.vendor_id) ??
                              vendor.vendor_id.slice(0, 8)}
                          </strong>
                          <span className="secondary-cell">
                            {vendor.vendor_id}
                          </span>
                        </td>
                        <td className="numeric">
                          {money(vendor.current_cents)}
                        </td>
                        <td className="numeric">
                          {money(vendor.days_1_30_cents)}
                        </td>
                        <td className="numeric">
                          {money(vendor.days_31_60_cents)}
                        </td>
                        <td className="numeric">
                          {money(vendor.days_61_90_cents)}
                        </td>
                        <td className="numeric">
                          {money(vendor.days_90_plus_cents)}
                        </td>
                        <td className="numeric balance-cell">
                          {money(vendor.total_outstanding_cents)}
                        </td>
                        <td className="numeric">
                          {percentage(vendor.share_pct)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <footer className="pagination">
                <span>
                  Page {report.page} of {Math.max(report.total_pages, 1)}
                  {" · "}
                  {report.total_count} vendors
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