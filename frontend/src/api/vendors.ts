import { apiRequest } from "./client";

export interface Vendor {
  id: string;
  name: string;
  email: string | null;
  is_active: boolean;
}
export interface VendorCreateInput {
  name: string;
  email: string | null;
}

export interface VendorReplaceInput {
  name: string;
  email: string | null;
  is_active: boolean;
}
interface VendorPage {
  items: Vendor[];
  total: number;
  limit: number;
  offset: number;
}

export function getVendors(): Promise<VendorPage> {
  return apiRequest<VendorPage>("/vendors?limit=100&offset=0");
}

export function createVendor(input: VendorCreateInput): Promise<Vendor> {
  return apiRequest<Vendor>("/vendors", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateVendor(
  vendorId: string,
  input: VendorReplaceInput,
): Promise<Vendor> {
  return apiRequest<Vendor>(`/vendors/${vendorId}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function deleteVendor(vendorId: string): Promise<void> {
  return apiRequest<void>(`/vendors/${vendorId}`, {
    method: "DELETE",
  });
}