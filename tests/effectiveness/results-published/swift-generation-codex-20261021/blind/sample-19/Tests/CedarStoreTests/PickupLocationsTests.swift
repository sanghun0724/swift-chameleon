import Testing
@testable import CedarStore

struct PickupLocationsTests {
    @Test func blankPostcodesDoNotCallAPI() async {
        let api = StubShopAPI()
        let graph = StoreGraph(api: api)
        for postcode in ["", " ", "\t\r\n", "\u{2003}"] {
            expectIssue(await graph.loadPickupLocations.execute(postcode: postcode), .invalidIdentifier)
        }
        #expect(api.postcodes.isEmpty)
    }

    @Test func filtersDeduplicatesAndSortsWhileForwardingPostcode() async {
        let api = StubShopAPI()
        api.pickupReply = .payload([
            .init(id: "b", title: "Inactive", capacity: 10, active: false),
            .init(id: "b", title: "Negative", capacity: -1, active: true),
            .init(id: "z", title: "Zulu", capacity: 3, active: true),
            .init(id: "b", title: "Alpha", capacity: 0, active: true),
            .init(id: "a", title: "Alpha", capacity: 2, active: true),
            .init(id: "b", title: "Aardvark", capacity: 99, active: true),
            .init(id: "inactive", title: "Hidden", capacity: 1, active: false),
            .init(id: "negative", title: "Hidden", capacity: -2, active: true)
        ])
        let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: " \tAB12\n")
        guard case .value(let locations) = result else {
            Issue.record("Expected pickup locations")
            return
        }
        #expect(locations == [
            PickupLocation(id: "a", title: "Alpha", capacity: 2),
            PickupLocation(id: "b", title: "Alpha", capacity: 0),
            PickupLocation(id: "z", title: "Zulu", capacity: 3)
        ])
        #expect(api.postcodes == [" \tAB12\n"])
    }

    @Test func emptyAndIneligibleCatalogsSucceed() async {
        let api = StubShopAPI()
        for rows: [PickupLocationDTO] in [
            [],
            [.init(id: "a", title: "A", capacity: 0, active: false),
             .init(id: "b", title: "B", capacity: -1, active: true)]
        ] {
            api.pickupReply = .payload(rows)
            let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: "123")
            guard case .value(let locations) = result else {
                Issue.record("Expected a successful empty catalog")
                continue
            }
            #expect(locations.isEmpty)
        }
    }

    @Test func preservesTransportFailureMapping() async {
        let api = StubShopAPI()
        for (transport, domain): (TransportIssue, ShopIssue) in [
            (.offline, .unavailable), (.forbidden, .unauthorized)
        ] {
            api.pickupReply = .failure(transport)
            expectIssue(await StoreGraph(api: api).loadPickupLocations.execute(postcode: "123"), domain)
        }
    }

    @Test func existingGraphFeaturesStillWork() async {
        let graph = StoreGraph(api: StubShopAPI())
        let results = [
            await graph.loadOrderSummary.execute(id: "order"),
            await graph.loadAccountName.execute(id: "account"),
            await graph.loadBasketName.execute(id: "basket")
        ]
        for (result, expected) in zip(results, ["order", "account", "basket"]) {
            guard case .value(let value) = result else {
                Issue.record("Expected existing feature to succeed")
                continue
            }
            #expect(value == expected)
        }
    }

    private func expectIssue<T>(_ result: ShopResult<T>, _ expected: ShopIssue) {
        guard case .issue(let issue) = result else {
            Issue.record("Expected issue \(expected)")
            return
        }
        #expect(issue == expected)
    }
}

private final class StubShopAPI: ShopAPI {
    var postcodes: [String] = []
    var pickupReply: TransportReply<[PickupLocationDTO]> = .payload([])

    func pickupLocations(postcode: String) async -> TransportReply<[PickupLocationDTO]> {
        postcodes.append(postcode)
        return pickupReply
    }

    func orderSummary(id: String) async -> TransportReply<String> { .payload(id) }
    func accountName(id: String) async -> TransportReply<String> { .payload(id) }
    func basketName(id: String) async -> TransportReply<String> { .payload(id) }
    func shippingQuote(orderID: String) async -> TransportReply<ShippingQuoteDTO> {
        .failure(.offline)
    }
}
