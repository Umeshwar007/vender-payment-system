import { apiRequest } from "./client";

export interface Vendor {
  id: string;
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