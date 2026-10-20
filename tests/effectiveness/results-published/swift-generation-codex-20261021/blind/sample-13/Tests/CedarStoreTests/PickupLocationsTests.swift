import Testing
@testable import CedarStore

struct PickupLocationsTests {
    @Test func filtersDeduplicatesSortsAndPreservesPostcode() async {
        let api = StubShopAPI()
        api.pickupReply = .payload([
            .init(id: "a", title: "Inactive", capacity: 5, active: false),
            .init(id: "a", title: "Negative", capacity: -1, active: true),
            .init(id: "z", title: "Alpha", capacity: 2, active: true),
            .init(id: "b", title: "Same", capacity: 3, active: true),
            .init(id: "a", title: "Same", capacity: 0, active: true),
            .init(id: "a", title: "Earlier", capacity: 9, active: true)
        ])

        let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: " AB12 \n")

        expectValue(result, [
            PickupLocation(id: "z", title: "Alpha", capacity: 2),
            PickupLocation(id: "a", title: "Same", capacity: 0),
            PickupLocation(id: "b", title: "Same", capacity: 3)
        ])
        #expect(api.postcodes == [" AB12 \n"])
    }

    @Test func blankPostcodesDoNotCallAPI() async {
        let api = StubShopAPI()
        let graph = StoreGraph(api: api)
        for postcode in ["", " ", "\t\r\n", "\u{2003}"] {
            expectIssue(await graph.loadPickupLocations.execute(postcode: postcode), .invalidIdentifier)
        }
        #expect(api.postcodes.isEmpty)
    }

    @Test func emptyAndIneligiblePayloadsSucceed() async {
        let api = StubShopAPI()
        let graph = StoreGraph(api: api)
        expectValue(await graph.loadPickupLocations.execute(postcode: "123"), [])
        api.pickupReply = .payload([
            .init(id: "a", title: "Inactive", capacity: 1, active: false),
            .init(id: "b", title: "Negative", capacity: -1, active: true)
        ])
        expectValue(await graph.loadPickupLocations.execute(postcode: "123"), [])
    }

    @Test func transportFailuresKeepDomainMapping() async {
        let api = StubShopAPI()
        let graph = StoreGraph(api: api)
        api.pickupReply = .failure(.offline)
        expectIssue(await graph.loadPickupLocations.execute(postcode: "123"), .unavailable)
        api.pickupReply = .failure(.forbidden)
        expectIssue(await graph.loadPickupLocations.execute(postcode: "123"), .unauthorized)
    }

    @Test func existingGraphFeaturesStillWork() async {
        let graph = StoreGraph(api: StubShopAPI())
        expectValue(await graph.loadOrderSummary.execute(id: "order"), "Order")
        expectValue(await graph.loadAccountName.execute(id: "account"), "Account")
        expectValue(await graph.loadBasketName.execute(id: "basket"), "Basket")
    }
}

private func expectValue<Value: Equatable>(_ result: ShopResult<Value>, _ expected: Value) {
    switch result {
    case .value(let value): #expect(value == expected)
    case .issue(let issue): Issue.record("Expected value, received \(issue)")
    }
}

private func expectIssue<Value>(_ result: ShopResult<Value>, _ expected: ShopIssue) {
    switch result {
    case .value: Issue.record("Expected issue \(expected), received value")
    case .issue(let issue): #expect(issue == expected)
    }
}

private final class StubShopAPI: ShopAPI {
    var postcodes: [String] = []
    var pickupReply: TransportReply<[PickupLocationDTO]> = .payload([])

    func pickupLocations(postcode: String) async -> TransportReply<[PickupLocationDTO]> {
        postcodes.append(postcode)
        return pickupReply
    }

    func orderSummary(id: String) async -> TransportReply<String> { .payload("Order") }
    func accountName(id: String) async -> TransportReply<String> { .payload("Account") }
    func basketName(id: String) async -> TransportReply<String> { .payload("Basket") }
    func shippingQuote(orderID: String) async -> TransportReply<ShippingQuoteDTO> {
        .payload(.init(cents: 0, currency: "USD"))
    }
}
