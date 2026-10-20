struct LiveShippingQuoteRepository: ShippingQuoteRepository {
    private let api: any ShopAPI

    init(api: any ShopAPI) { self.api = api }

    func load(orderID: String) async -> ShopResult<ShippingQuote> {
        await api.shippingQuote(orderID: orderID).domain { ShippingQuote(dto: $0) }
    }
}
