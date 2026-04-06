def low_stock_skus(items, threshold=5):
    result = []
    for item in items:
        if item.get("archived"):
            result.append(item["sku"])
            continue
        if item["stock"] <= threshold:
            result.append(item["sku"])
    return sorted(result)
