import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createVendor,
  deleteVendor,
  getVendors,
  updateVendor,
  type Vendor,
} from "../api/vendors";

function VendorRow({ vendor }: { vendor: Vendor }) {
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
    <tr>
      <td>
        <input
          aria-label={`Name for ${vendor.name}`}
          value={name}
          maxLength={200}
          onChange={(event) => setName(event.target.value)}
        />
      </td>
      <td>
        <input
          aria-label={`Email for ${vendor.name}`}
          type="email"
          value={email}
          maxLength={320}
          onChange={(event) => setEmail(event.target.value)}
        />
      </td>
      <td>{vendor.is_active ? "Active" : "Inactive"}</td>
      <td>
        <button
          type="button"
          disabled={updateMutation.isPending || !name.trim()}
          onClick={() => updateMutation.mutate(vendor.is_active)}
        >
          Save
        </button>
        <button
          type="button"
          disabled={updateMutation.isPending}
          onClick={() => updateMutation.mutate(!vendor.is_active)}
        >
          {vendor.is_active ? "Deactivate" : "Reactivate"}
        </button>
        <button
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

        {updateMutation.isError && (
          <p className="form-error" role="alert">
            Couldn’t update vendor: {updateMutation.error.message}
          </p>
        )}
        {deleteMutation.isError && (
          <p className="form-error" role="alert">
            Couldn’t delete vendor: {deleteMutation.error.message}
          </p>
        )}
      </td>
    </tr>
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

  return (
    <section className="content-card">
      <div className="card-heading">
        <div>
          <h2>Vendors</h2>
          <p>Add and manage the vendors associated with invoices.</p>
        </div>
      </div>

      <form
        className="form-grid"
        onSubmit={(event) => {
          event.preventDefault();
          createMutation.mutate({
            name: name.trim(),
            email: email.trim() || null,
          });
        }}
      >
        <label className="form-field">
          <span>Vendor name</span>
          <input
            value={name}
            maxLength={200}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </label>
        <label className="form-field">
          <span>Email (optional)</span>
          <input
            type="email"
            value={email}
            maxLength={320}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <button
          className="primary-button"
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
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {vendorsQuery.data.items.map((vendor) => (
                <VendorRow key={vendor.id} vendor={vendor} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}