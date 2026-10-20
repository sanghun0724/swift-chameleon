protocol OrderSummaryRepository {
    func load(id: String) async -> ShopResult<String>
}
