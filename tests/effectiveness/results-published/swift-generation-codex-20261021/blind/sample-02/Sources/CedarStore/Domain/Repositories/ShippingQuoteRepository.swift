protocol ShippingQuoteRepository {
    func load(orderID: String) async -> ShopResult<ShippingQuote>
}
