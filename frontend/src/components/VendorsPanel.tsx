import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createVendor,
  deleteVendor,
  getVendors,
  updateVendor,
  type Vendor,
} from "../api/vendors";

function initials(name: string): string {
  return (
    name
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("") || "V"
  );
}

function VendorCard({ vendor }: { vendor: Vendor }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(vendor.name);
  const [email, setEmail] = useState(vendor.email ?? "");

  const updateMutation = useMutation({
    mutationFn: (isActive: boolean) =>
      updateVendor(vendor.id, {
        name: name.trim(),
        email: email.trim() || null,
        is_active: isActive,
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["vendors"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteVendor(vendor.id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["vendors"] }),
  });

  return (
    <article className="vendor-card">
      <div className="vendor-card-heading">
        <div className="vendor-avatar" aria-hidden="true">
          {initials(vendor.name)}
        </div>
        <div className="vendor-card-identity">
          <h3>{vendor.name}</h3>
          <span className="vendor-card-id">{vendor.id.slice(0, 8)}…</span>
        </div>
        <span
          className={
            vendor.is_active
              ? "vendor-status vendor-status-active"
              : "vendor-status vendor-status-inactive"
          }
        >
          {vendor.is_active ? "Active" : "Inactive"}
        </span>
      </div>

      <div className="vendor-card-fields">
        <label className="vendor-field">
          <span>Vendor name</span>
          <input
            value={name}
            maxLength={200}
            onChange={(event) => setName(event.target.value)}
          />
        </label>

        <label className="vendor-field">
          <span>Email</span>
          <input
            type="email"
            value={email}
            maxLength={320}
            placeholder="No email added"
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
      </div>

      {(updateMutation.isError || deleteMutation.isError) && (
        <p className="vendor-error" role="alert">
          {updateMutation.isError
            ? `Couldn’t update vendor: ${updateMutation.error.message}`
            : `Couldn’t delete vendor: ${deleteMutation.error?.message}`}
        </p>
      )}

      <div className="vendor-card-actions">
        <button
          className="vendor-button vendor-button-save"
          type="button"
          disabled={updateMutation.isPending || !name.trim()}
          onClick={() => updateMutation.mutate(vendor.is_active)}
        >
          {updateMutation.isPending ? "Saving…" : "Save changes"}
        </button>

        <button
          className="vendor-button vendor-button-secondary"
          type="button"
          disabled={updateMutation.isPending}
          onClick={() => updateMutation.mutate(!vendor.is_active)}
        >
          {vendor.is_active ? "Deactivate" : "Reactivate"}
        </button>

        <button
          className="vendor-button vendor-button-danger"
          type="button"
          disabled={deleteMutation.isPending}
          onClick={() => {
            if (window.confirm(`Delete vendor ${vendor.name}?`)) {
              deleteMutation.mutate();
            }
          }}
        >
          Delete
        </button>
      </div>
    </article>
  );
}

export default function VendorsPanel() {
  const queryClient = useQueryClient();
  const vendorsQuery = useQuery({
    queryKey: ["vendors"],
    queryFn: getVendors,
  });

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");

  const createMutation = useMutation({
    mutationFn: createVendor,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["vendors"] });
      setName("");
      setEmail("");
    },
  });

  const vendors = vendorsQuery.data?.items ?? [];

  return (
    <section className="content-card vendors-panel">
      <div className="vendors-panel-heading">
        <div>
          <p className="eyebrow">VENDOR DIRECTORY</p>
          <h2>Manage vendors</h2>
          <p className="vendors-subtitle">
            Keep supplier contact details and account status up to date.
          </p>
        </div>
        <span className="count-pill">
          {vendorsQuery.data ? `${vendorsQuery.data.total} vendors` : "Vendors"}
        </span>
      </div>

      <form
        className="vendor-create-card"
        onSubmit={(event) => {
          event.preventDefault();
          createMutation.mutate({
            name: name.trim(),
            email: email.trim() || null,
          });
        }}
      >
        <div className="vendor-create-copy">
          <span className="vendor-create-icon" aria-hidden="true">＋</span>
          <div>
            <h3>Add a vendor</h3>
            <p>Create a vendor profile for invoice entry.</p>
          </div>
        </div>

        <label className="vendor-field">
          <span>Vendor name</span>
          <input
            value={name}
            maxLength={200}
            placeholder="e.g. Northwind Supplies"
            onChange={(event) => setName(event.target.value)}
            required
          />
        </label>

        <label className="vendor-field">
          <span>Email <small>Optional</small></span>
          <input
            type="email"
            value={email}
            maxLength={320}
            placeholder="accounts@example.com"
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>

        <button
          className="vendor-button vendor-button-add"
          type="submit"
          disabled={createMutation.isPending}
        >
          {createMutation.isPending ? "Adding…" : "Add vendor"}
        </button>
      </form>

      {createMutation.isError && (
        <div className="notice notice-error" role="alert">
          Couldn’t add vendor: {createMutation.error.message}
        </div>
      )}

      {vendorsQuery.isPending && (
        <div className="notice" role="status">Loading vendors…</div>
      )}

      {vendorsQuery.isError && (
        <div className="notice notice-error" role="alert">
          Couldn’t load vendors: {vendorsQuery.error.message}
        </div>
      )}

      {vendorsQuery.data && (
        <div className="vendor-directory">
          <div className="vendor-directory-heading">
            <div>
              <h3>Your vendors</h3>
              <p>Edit details or change a vendor’s active status.</p>
            </div>
            <span>{vendorsQuery.data.total} total</span>
          </div>

          {vendors.length === 0 ? (
            <div className="empty-state">
              <h3>No vendors yet</h3>
              <p>Add a vendor above to get started.</p>
            </div>
          ) : (
            <div className="vendor-grid">
              {vendors.map((vendor) => (
                <VendorCard key={vendor.id} vendor={vendor} />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}