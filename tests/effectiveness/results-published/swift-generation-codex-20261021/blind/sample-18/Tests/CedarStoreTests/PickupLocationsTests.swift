import Testing
@testable import CedarStore

struct PickupLocationsTests {
    @Test func blankPostcodesSkipAPI() async {
        let api = StubShopAPI()
        let graph = StoreGraph(api: api)
        for postcode in ["", " ", "\t\r\n "] {
            assertIssue(await graph.loadPickupLocations.execute(postcode: postcode), .invalidIdentifier)
        }
        #expect(api.postcodes.isEmpty)
    }

    @Test func filtersBeforeDeduplicatingAndSortsByTitleThenID() async {
        let api = StubShopAPI()
        api.pickupReply = .payload([
            .init(id: "b", title: "Inactive", capacity: 4, active: false),
            .init(id: "b", title: "Negative", capacity: -1, active: true),
            .init(id: "z", title: "Zulu", capacity: 3, active: true),
            .init(id: "b", title: "Alpha", capacity: 0, active: true),
            .init(id: "a", title: "Alpha", capacity: 2, active: true),
            .init(id: "b", title: "Aardvark", capacity: 9, active: true),
            .init(id: "inactive", title: "Hidden", capacity: 1, active: false),
            .init(id: "negative", title: "Hidden", capacity: -2, active: true)
        ])
        let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: "  AB12 \n")
        guard case .value(let locations) = result else {
            Issue.record("Expected pickup locations")
            return
        }
        #expect(locations == [
            PickupLocation(id: "a", title: "Alpha", capacity: 2),
            PickupLocation(id: "b", title: "Alpha", capacity: 0),
            PickupLocation(id: "z", title: "Zulu", capacity: 3)
        ])
        #expect(api.postcodes == ["  AB12 \n"])
    }

    @Test func emptyAndIneligibleCatalogsSucceed() async {
        let api = StubShopAPI()
        for rows: [PickupLocationDTO] in [
            [],
            [.init(id: "a", title: "Hidden", capacity: 0, active: false)]
        ] {
            api.pickupReply = .payload(rows)
            let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: "123")
            guard case .value(let locations) = result else {
                Issue.record("Expected an empty successful catalog")
                continue
            }
            #expect(locations.isEmpty)
        }
    }

    @Test func transportFailuresRetainDomainMapping() async {
        let api = StubShopAPI()
        for (failure, expected) in [
            (TransportIssue.offline, ShopIssue.unavailable),
            (.forbidden, .unauthorized)
        ] {
            api.pickupReply = .failure(failure)
            assertIssue(await StoreGraph(api: api).loadPickupLocations.execute(postcode: "123"), expected)
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

    private func assertIssue<Value>(_ result: ShopResult<Value>, _ expected: ShopIssue) {
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
        .payload(.init(cents: 0, currency: "USD"))
    }
}
