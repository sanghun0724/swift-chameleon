import Testing
@testable import CedarStore

struct PickupLocationsTests {
    @Test func rejectsBlankPostcodesWithoutCallingAPI() async {
        let api = StubShopAPI()
        let graph = StoreGraph(api: api)
        for postcode in ["", " ", "\t\r\n", " \u{2003}\n"] {
            guard case .issue(.invalidIdentifier) = await graph.loadPickupLocations.execute(postcode: postcode) else {
                Issue.record("Expected invalidIdentifier")
                continue
            }
        }
        #expect(api.postcodes.isEmpty)
    }

    @Test func filtersDeduplicatesSortsAndForwardsPostcodeUnchanged() async {
        let api = StubShopAPI()
        api.pickupReply = .payload([
            .init(id: "b", title: "Inactive", capacity: 5, active: false),
            .init(id: "b", title: "Negative", capacity: -1, active: true),
            .init(id: "z", title: "Zulu", capacity: 3, active: true),
            .init(id: "b", title: "Alpha", capacity: 0, active: true),
            .init(id: "b", title: "Earlier title", capacity: 9, active: true),
            .init(id: "a", title: "Alpha", capacity: 2, active: true),
            .init(id: "inactive", title: "Hidden", capacity: 1, active: false),
            .init(id: "negative", title: "Hidden", capacity: -1, active: true)
        ])
        let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: " \tAB12 3CD\n")
        guard case .value(let locations) = result else {
            Issue.record("Expected pickup locations")
            return
        }
        #expect(locations == [
            PickupLocation(id: "a", title: "Alpha", capacity: 2),
            PickupLocation(id: "b", title: "Alpha", capacity: 0),
            PickupLocation(id: "z", title: "Zulu", capacity: 3)
        ])
        #expect(api.postcodes == [" \tAB12 3CD\n"])
    }

    @Test func emptyAndIneligibleCatalogsSucceedWithEmptyResults() async {
        let api = StubShopAPI()
        for rows: [PickupLocationDTO] in [
            [],
            [.init(id: "a", title: "Hidden", capacity: 0, active: false),
             .init(id: "b", title: "Hidden", capacity: -1, active: true)]
        ] {
            api.pickupReply = .payload(rows)
            guard case .value(let locations) = await StoreGraph(api: api).loadPickupLocations.execute(postcode: "123") else {
                Issue.record("Expected successful empty catalog")
                continue
            }
            #expect(locations.isEmpty)
        }
    }

    @Test func preservesTransportFailureMapping() async {
        let api = StubShopAPI()
        for (transport, expected): (TransportIssue, ShopIssue) in [
            (.offline, .unavailable), (.forbidden, .unauthorized)
        ] {
            api.pickupReply = .failure(transport)
            guard case .issue(let issue) = await StoreGraph(api: api).loadPickupLocations.execute(postcode: "123") else {
                Issue.record("Expected transport failure")
                continue
            }
            #expect(issue == expected)
        }
        #expect(api.postcodes == ["123", "123"])
    }

    @Test func existingGraphFeaturesStillLoad() async {
        let graph = StoreGraph(api: StubShopAPI())
        let results = [
            await graph.loadOrderSummary.execute(id: "order"),
            await graph.loadAccountName.execute(id: "account"),
            await graph.loadBasketName.execute(id: "basket")
        ]
        for (result, expected) in zip(results, ["Order", "Account", "Basket"]) {
            guard case .value(let value) = result else {
                Issue.record("Expected existing feature to succeed")
                continue
            }
            #expect(value == expected)
        }
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
