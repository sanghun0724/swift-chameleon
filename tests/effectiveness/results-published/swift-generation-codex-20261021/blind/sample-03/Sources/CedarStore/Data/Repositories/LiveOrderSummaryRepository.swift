struct LiveOrderSummaryRepository: OrderSummaryRepository {
    private let api: any ShopAPI

    init(api: any ShopAPI) { self.api = api }

    func load(id: String) async -> ShopResult<String> {
        await api.orderSummary(id: id).domain { $0.isEmpty ? nil : $0 }
    }
}
