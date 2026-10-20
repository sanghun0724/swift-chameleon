import Testing
@testable import CedarStore

struct PickupLocationsTests {
    @Test func blankPostcodesDoNotCallAPI() async {
        let api = StubShopAPI()
        let graph = StoreGraph(api: api)

        for postcode in ["", " ", "\t\r\n", "\u{2003}"] {
            assertIssue(await graph.loadPickupLocations.execute(postcode: postcode), .invalidIdentifier)
        }
        #expect(api.postcodes.isEmpty)
    }

    @Test func forwardsPostcodeAndReturnsFirstEligibleLocationsInOrder() async {
        let api = StubShopAPI()
        api.pickupReply = .payload([
            .init(id: "a", title: "Inactive", capacity: 5, active: false),
            .init(id: "a", title: "Negative", capacity: -1, active: true),
            .init(id: "z", title: "Zulu", capacity: 2, active: true),
            .init(id: "b", title: "Alpha", capacity: 3, active: true),
            .init(id: "a", title: "Alpha", capacity: 0, active: true),
            .init(id: "a", title: "Duplicate", capacity: 9, active: true),
            .init(id: "x", title: "Excluded", capacity: -1, active: true),
            .init(id: "y", title: "Excluded", capacity: 1, active: false),
        ])

        let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: "  AB12 \n")

        #expect(api.postcodes == ["  AB12 \n"])
        guard case .value(let locations) = result else {
            Issue.record("Expected pickup locations")
            return
        }
        #expect(locations == [
            PickupLocation(id: "a", title: "Alpha", capacity: 0),
            PickupLocation(id: "b", title: "Alpha", capacity: 3),
            PickupLocation(id: "z", title: "Zulu", capacity: 2),
        ])
    }

    @Test func emptyCatalogsSucceed() async {
        let api = StubShopAPI()
        for rows: [PickupLocationDTO] in [
            [],
            [.init(id: "a", title: "Inactive", capacity: 0, active: false)],
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

    @Test func transportFailuresKeepTheirDomainMapping() async {
        let api = StubShopAPI()
        let graph = StoreGraph(api: api)
        api.pickupReply = .failure(.offline)
        assertIssue(await graph.loadPickupLocations.execute(postcode: "123"), .unavailable)
        api.pickupReply = .failure(.forbidden)
        assertIssue(await graph.loadPickupLocations.execute(postcode: "123"), .unauthorized)
    }

    @Test func existingGraphFeaturesStillWork() async {
        let graph = StoreGraph(api: StubShopAPI())
        let results = [
            await graph.loadOrderSummary.execute(id: "order"),
            await graph.loadAccountName.execute(id: "account"),
            await graph.loadBasketName.execute(id: "basket"),
        ]
        for result in results {
            guard case .value(let value) = result else {
                Issue.record("Expected existing feature to succeed")
                continue
            }
            #expect(value == "Existing value")
        }
        assertIssue(await graph.loadOrderSummary.execute(id: " "), .invalidIdentifier)
        assertIssue(await graph.loadAccountName.execute(id: " "), .invalidIdentifier)
        assertIssue(await graph.loadBasketName.execute(id: " "), .invalidIdentifier)
    }
}

private func assertIssue<Value>(_ result: ShopResult<Value>, _ expected: ShopIssue) {
    guard case .issue(let issue) = result else {
        Issue.record("Expected issue \(expected)")
        return
    }
    #expect(issue == expected)
}

private final class StubShopAPI: ShopAPI {
    var postcodes: [String] = []
    var pickupReply: TransportReply<[PickupLocationDTO]> = .payload([])

    func pickupLocations(postcode: String) async -> TransportReply<[PickupLocationDTO]> {
        postcodes.append(postcode)
        return pickupReply
    }

    func orderSummary(id: String) async -> TransportReply<String> { .payload("Existing value") }
    func accountName(id: String) async -> TransportReply<String> { .payload("Existing value") }
    func basketName(id: String) async -> TransportReply<String> { .payload("Existing value") }
    func shippingQuote(orderID: String) async -> TransportReply<ShippingQuoteDTO> {
        .payload(.init(cents: 0, currency: "USD"))
    }
}
