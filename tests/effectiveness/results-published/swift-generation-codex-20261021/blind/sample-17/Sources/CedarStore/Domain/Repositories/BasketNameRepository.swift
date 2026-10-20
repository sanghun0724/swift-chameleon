protocol BasketNameRepository {
    func load(id: String) async -> ShopResult<String>
}
