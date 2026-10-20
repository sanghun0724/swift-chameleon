struct LiveShippingQuoteRepository: ShippingQuoteRepository {
    private let api: any ShopAPI

    init(api: any ShopAPI) { self.api = api }

    func quote(orderID: String) async -> ShopResult<ShippingQuote> {
        await api.shippingQuote(orderID: orderID).domain { ShippingQuote(dto: $0) }
    }
}
