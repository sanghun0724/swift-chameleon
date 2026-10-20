import Testing
@testable import CedarStore

struct PickupLocationsTests {
    @Test func filtersDeduplicatesAndSortsEligibleLocations() async {
        let api = StubShopAPI(pickupReply: .payload([
            .init(id: "b", title: "Ignored", capacity: 1, active: false),
            .init(id: "a", title: "Ignored", capacity: -1, active: true),
            .init(id: "b", title: "Central", capacity: 0, active: true),
            .init(id: "a", title: "Central", capacity: 2, active: true),
            .init(id: "b", title: "Duplicate", capacity: 9, active: true),
            .init(id: "z", title: "Airport", capacity: 3, active: true),
        ]))
        let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: " AB12 \n")
        guard case .value(let locations) = result else {
            Issue.record("Expected pickup locations")
            return
        }
        #expect(locations == [
            PickupLocation(id: "z", title: "Airport", capacity: 3),
            PickupLocation(id: "a", title: "Central", capacity: 2),
            PickupLocation(id: "b", title: "Central", capacity: 0),
        ])
        #expect(api.postcodes == [" AB12 \n"])
    }

    @Test func blankPostcodesDoNotCallAPI() async {
        let api = StubShopAPI(pickupReply: .payload([]))
        for postcode in ["", " ", "\t\n\r"] {
            let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: postcode)
            guard case .issue(.invalidIdentifier) = result else {
                Issue.record("Expected invalidIdentifier")
                continue
            }
        }
        #expect(api.postcodes.isEmpty)
    }

    @Test func emptyCatalogsSucceed() async {
        for rows: [PickupLocationDTO] in [
            [],
            [.init(id: "a", title: "Closed", capacity: 1, active: false)],
        ] {
            let api = StubShopAPI(pickupReply: .payload(rows))
            let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: "123")
            guard case .value(let locations) = result else {
                Issue.record("Expected a successful empty catalog")
                continue
            }
            #expect(locations.isEmpty)
        }
    }

    @Test func transportFailuresKeepDomainMapping() async {
        for (failure, expected): (TransportIssue, ShopIssue) in [
            (.offline, .unavailable), (.forbidden, .unauthorized),
        ] {
            let api = StubShopAPI(pickupReply: .failure(failure))
            let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: "123")
            guard case .issue(let issue) = result else {
                Issue.record("Expected a domain issue")
                continue
            }
            #expect(issue == expected)
        }
    }

    @Test func existingGraphFeaturesStillLoad() async {
        let graph = StoreGraph(api: StubShopAPI(pickupReply: .payload([])))
        for result in [
            await graph.loadOrderSummary.execute(id: "123"),
            await graph.loadAccountName.execute(id: "123"),
            await graph.loadBasketName.execute(id: "123"),
        ] {
            guard case .value(let name) = result else {
                Issue.record("Expected existing feature to load")
                continue
            }
            #expect(name == "Existing")
        }
    }
}

private final class StubShopAPI: ShopAPI {
    let pickupReply: TransportReply<[PickupLocationDTO]>
    var postcodes: [String] = []

    init(pickupReply: TransportReply<[PickupLocationDTO]>) {
        self.pickupReply = pickupReply
    }

    func pickupLocations(postcode: String) async -> TransportReply<[PickupLocationDTO]> {
        postcodes.append(postcode)
        return pickupReply
    }

    func orderSummary(id: String) async -> TransportReply<String> { .payload("Existing") }
    func accountName(id: String) async -> TransportReply<String> { .payload("Existing") }
    func basketName(id: String) async -> TransportReply<String> { .payload("Existing") }
    func shippingQuote(orderID: String) async -> TransportReply<ShippingQuoteDTO> {
        .payload(.init(cents: 0, currency: "USD"))
    }
}
