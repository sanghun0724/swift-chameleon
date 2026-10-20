protocol AccountNameRepository {
    func load(id: String) async -> ShopResult<String>
}
