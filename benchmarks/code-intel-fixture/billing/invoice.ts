export type Invoice = { id: string; cents: number };

export function calculateTax(invoice: Invoice): number {
  return Math.round(invoice.cents * 0.08);
}

export function invoiceTotal(invoice: Invoice): number {
  return invoice.cents + calculateTax(invoice);
}

export function renderInvoice(invoice: Invoice): string {
  return `${invoice.id}:${invoiceTotal(invoice)}`;
}
