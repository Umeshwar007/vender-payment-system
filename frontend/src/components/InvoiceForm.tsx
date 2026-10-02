
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
    createInvoice,
    type InvoiceCreateInput,
    getInvoice,
    updateInvoice,
    type InvoiceUpdateInput,
} from "../api/invoices";
import { getVendors } from "../api/vendors";

interface InvoiceFormProps {
    invoiceId?: string;
    onClose: () => void;
    onCreated: () => void;
}

interface LineDraft {
    description: string;
    quantity: string;
    unitPrice: string;
}

function dollarsToCents(value: string): number | null {
    const match = value.trim().match(/^(\d+)(?:\.(\d{1,2}))?$/);
    if (!match) return null;

    const wholeDollars = Number(match[1]);
    const cents = Number((match[2] ?? "").padEnd(2, "0"));
    const result = wholeDollars * 100 + cents;

    return Number.isSafeInteger(result) ? result : null;
}

export default function InvoiceForm({
    invoiceId,
    onClose,
    onCreated,
}: InvoiceFormProps) {
    const queryClient = useQueryClient();
    const vendorsQuery = useQuery({
        queryKey: ["vendors"],
        queryFn: getVendors,
        enabled: !invoiceId,
    });
    const invoiceQuery = useQuery({
        queryKey: ["invoice", invoiceId],
        queryFn: () => getInvoice(invoiceId!),
        enabled: Boolean(invoiceId),
    });

    const [vendorId, setVendorId] = useState("");
    const [invoiceNumber, setInvoiceNumber] = useState("");
    const [issuedDate, setIssuedDate] = useState("");
    const [dueDate, setDueDate] = useState("");
    const [lines, setLines] = useState<LineDraft[]>([
        { description: "", quantity: "1", unitPrice: "" },
    ]);
    const [validationError, setValidationError] = useState("");



    useEffect(() => {
        const invoice = invoiceQuery.data;
        if (!invoice) return;

        setVendorId(invoice.vendor_id);
        setInvoiceNumber(invoice.invoice_number);
        setIssuedDate(invoice.issued_date);
        setDueDate(invoice.due_date);
        setLines(
            invoice.lines.map((line) => ({
                description: line.description,
                quantity: String(line.quantity),
                unitPrice: (line.unit_price_cents / 100).toFixed(2),
            })),
        );
    }, [invoiceQuery.data]);
    const saveMutation = useMutation({
        mutationFn: (payload: InvoiceCreateInput | InvoiceUpdateInput) =>
            invoiceId
                ? updateInvoice(invoiceId, payload as InvoiceUpdateInput)
                : createInvoice(payload as InvoiceCreateInput),
        onSuccess: async () => {
            await queryClient.invalidateQueries({ queryKey: ["invoices"] });
            onCreated();
        },
    });

    const activeVendors =
        vendorsQuery.data?.items.filter((vendor) => vendor.is_active) ?? [];

    function updateLine(index: number, changes: Partial<LineDraft>) {
        setLines((current) =>
            current.map((line, lineIndex) =>
                lineIndex === index ? { ...line, ...changes } : line,
            ),
        );
    }

    function submit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setValidationError("");

        if (!vendorId) {
            setValidationError("Choose a vendor.");
            return;
        }

        if (!issuedDate || !dueDate || dueDate < issuedDate) {
            setValidationError("The due date must be on or after the issue date.");
            return;
        }

        const requestLines = [];
        for (const line of lines) {
            const quantity = Number(line.quantity);
            const unitPriceCents = dollarsToCents(line.unitPrice);

            if (!line.description.trim()) {
                setValidationError("Each line needs a description.");
                return;
            }
            if (!Number.isInteger(quantity) || quantity <= 0) {
                setValidationError("Quantity must be a positive whole number.");
                return;
            }
            if (unitPriceCents === null) {
                setValidationError(
                    "Enter each unit price with up to two decimal places.",
                );
                return;
            }

            requestLines.push({
                description: line.description.trim(),
                quantity,
                unit_price_cents: unitPriceCents,
            });
        }

        const fields = {
            invoice_number: invoiceNumber.trim(),
            issued_date: issuedDate,
            due_date: dueDate,
            lines: requestLines,
        };

        if (invoiceId) {
            saveMutation.mutate(fields);
        } else {
            saveMutation.mutate({ vendor_id: vendorId, ...fields });
        }
    }

    return (
        <div className="modal-backdrop">
            <section
                className="invoice-dialog"
                role="dialog"
                aria-modal="true"
                aria-labelledby="new-invoice-title"
            >
                <div className="dialog-heading">
                    <div>
                        <p className="eyebrow">INVOICE WORKSPACE</p>
                        <h2 id="new-invoice-title">
                            {invoiceId ? "Edit draft invoice" : "Create invoice"}
                        </h2>
                    </div>
                    <button
                        className="icon-button"
                        type="button"
                        onClick={onClose}
                        aria-label="Close form"
                    >
                        ×
                    </button>
                </div>

                <form onSubmit={submit}>
                    {!invoiceId && (
                        <>
                            <label className="form-field">
                                <span>Vendor</span>
                                <select
                                    value={vendorId}
                                    onChange={(event) => setVendorId(event.target.value)}
                                    required
                                >
                                    <option value="">Choose a vendor</option>
                                    {activeVendors.map((vendor) => (
                                        <option key={vendor.id} value={vendor.id}>
                                            {vendor.name}
                                        </option>
                                    ))}
                                </select>
                            </label>

                            {vendorsQuery.isLoading && (
                                <p className="form-hint">Loading vendors…</p>
                            )}
                            {vendorsQuery.isError && (
                                <p className="form-error" role="alert">
                                    Couldn’t load vendors: {vendorsQuery.error.message}
                                </p>
                            )}
                            {!vendorsQuery.isLoading && activeVendors.length === 0 && (
                                <p className="form-hint">
                                    No active vendors are available. Add a vendor before creating an invoice.
                                </p>
                            )}
                        </>
                    )}
                    <label className="form-field">
                        <span>Invoice number</span>
                        <input
                            value={invoiceNumber}
                            onChange={(event) => setInvoiceNumber(event.target.value)}
                            maxLength={100}
                            required
                        />
                    </label>

                    <div className="form-grid">
                        <label className="form-field">
                            <span>Issue date</span>
                            <input
                                type="date"
                                value={issuedDate}
                                onChange={(event) => setIssuedDate(event.target.value)}
                                required
                            />
                        </label>
                        <label className="form-field">
                            <span>Due date</span>
                            <input
                                type="date"
                                value={dueDate}
                                onChange={(event) => setDueDate(event.target.value)}
                                min={issuedDate || undefined}
                                required
                            />
                        </label>
                    </div>

                    <div className="line-items-heading">
                        <h3>Line items</h3>
                        <button
                            className="text-button"
                            type="button"
                            onClick={() =>
                                setLines((current) => [
                                    ...current,
                                    { description: "", quantity: "1", unitPrice: "" },
                                ])
                            }
                        >
                            + Add line
                        </button>
                    </div>

                    {lines.map((line, index) => (
                        <div className="line-item" key={index}>
                            <label className="form-field line-description">
                                <span>Description</span>
                                <input
                                    value={line.description}
                                    onChange={(event) =>
                                        updateLine(index, { description: event.target.value })
                                    }
                                    maxLength={500}
                                    required
                                />
                            </label>
                            <label className="form-field line-quantity">
                                <span>Qty</span>
                                <input
                                    type="number"
                                    min="1"
                                    step="1"
                                    value={line.quantity}
                                    onChange={(event) =>
                                        updateLine(index, { quantity: event.target.value })
                                    }
                                    required
                                />
                            </label>
                            <label className="form-field line-price">
                                <span>Unit price ($)</span>
                                <input
                                    inputMode="decimal"
                                    placeholder="0.00"
                                    value={line.unitPrice}
                                    onChange={(event) =>
                                        updateLine(index, { unitPrice: event.target.value })
                                    }
                                    required
                                />
                            </label>
                            <button
                                className="icon-button remove-line"
                                type="button"
                                onClick={() =>
                                    setLines((current) =>
                                        current.filter((_, lineIndex) => lineIndex !== index),
                                    )
                                }
                                disabled={lines.length === 1}
                                aria-label={`Remove line ${index + 1}`}
                            >
                                ×
                            </button>
                        </div>
                    ))}

                    {(validationError || saveMutation.isError) && (
                        <p className="form-error" role="alert">
                            {validationError || saveMutation.error?.message}
                        </p>
                    )}

                    <div className="dialog-actions">
                        <button className="secondary-button" type="button" onClick={onClose}>
                            Cancel
                        </button>
                        <button
                            className="primary-button"
                            type="submit"
                            disabled={
                                saveMutation.isPending ||
                                vendorsQuery.isLoading ||
                                activeVendors.length === 0
                            }
                        >
                            {saveMutation.isPending ? "Saving…" : invoiceId ? "Update invoice" : "Create invoice"}
                        </button>
                    </div>
                </form>
            </section>
        </div>
    );
}