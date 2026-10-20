struct LivePickupLocationsRepository: PickupLocationsRepository {
    private let api: any ShopAPI

    init(api: any ShopAPI) { self.api = api }

    func load(postcode: String) async -> ShopResult<[PickupLocation]> {
        await api.pickupLocations(postcode: postcode).domain { PickupCatalog.available($0) }
    }
}
