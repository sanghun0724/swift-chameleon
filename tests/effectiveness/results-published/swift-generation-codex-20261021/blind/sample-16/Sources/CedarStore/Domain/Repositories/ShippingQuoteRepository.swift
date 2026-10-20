protocol ShippingQuoteRepository {
    func quote(orderID: String) async -> ShopResult<ShippingQuote>
}
