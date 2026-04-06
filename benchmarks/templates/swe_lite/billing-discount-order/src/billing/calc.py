def invoice_total(subtotal, tax_rate, discount=0.0):
    taxed = subtotal * (1 + tax_rate)
    return round(taxed - discount, 2)
