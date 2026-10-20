protocol PickupLocationsRepository {
    func load(postcode: String) async -> ShopResult<[PickupLocation]>
}
