struct CustomerGateway {
    let api: any ShopAPI
    func fetch(id: String) async -> String? {
        switch await api.accountName(id: id) {
        case .payload(let value): return value
        case .failure: return nil
        }
    }
}
