struct ReceiptGateway {
    private let api: any ShopAPI
    init(api: any ShopAPI) { self.api = api }

    func fetch(id: String) async -> String? {
        switch await api.orderSummary(id: id) {
        case .payload(let value): return value
        case .failure: return nil
        }
    }
}
