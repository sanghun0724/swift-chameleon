import Testing
@testable import CedarStore

struct PickupLocationsTests {
    @Test func filtersDeduplicatesAndSortsLocations() async {
        let api = ShopAPIStub(reply: .payload([
            .init(id: "b", title: "Inactive", capacity: 5, active: false),
            .init(id: "b", title: "Negative", capacity: -1, active: true),
            .init(id: "b", title: "Same", capacity: 0, active: true),
            .init(id: "b", title: "Duplicate", capacity: 9, active: true),
            .init(id: "z", title: "Alpha", capacity: 2, active: true),
            .init(id: "a", title: "Same", capacity: 3, active: true),
            .init(id: "x", title: "Excluded", capacity: -2, active: true),
            .init(id: "y", title: "Excluded", capacity: 1, active: false)
        ]))
        let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: "  AB12 \n")
        guard case .value(let locations) = result else {
            Issue.record("Expected locations")
            return
        }
        #expect(locations == [
            PickupLocation(id: "z", title: "Alpha", capacity: 2),
            PickupLocation(id: "a", title: "Same", capacity: 3),
            PickupLocation(id: "b", title: "Same", capacity: 0)
        ])
        #expect(api.postcodes == ["  AB12 \n"])
    }

    @Test func rejectsBlankPostcodesWithoutCallingAPI() async {
        let api = ShopAPIStub(reply: .payload([]))
        for postcode in ["", " ", "\t\r\n", "\u{2003}"] {
            let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: postcode)
            guard case .issue(.invalidIdentifier) = result else {
                Issue.record("Expected invalidIdentifier")
                continue
            }
        }
        #expect(api.postcodes.isEmpty)
    }

    @Test func emptyCatalogsAreSuccessful() async {
        for rows: [PickupLocationDTO] in [
            [],
            [.init(id: "a", title: "Inactive", capacity: 1, active: false)]
        ] {
            let api = ShopAPIStub(reply: .payload(rows))
            let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: "123")
            guard case .value(let locations) = result else {
                Issue.record("Expected successful empty catalog")
                continue
            }
            #expect(locations.isEmpty)
        }
    }

    @Test func preservesTransportFailures() async {
        for (failure, expected) in [
            (TransportIssue.offline, ShopIssue.unavailable),
            (.forbidden, .unauthorized)
        ] {
            let api = ShopAPIStub(reply: .failure(failure))
            let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: "123")
            guard case .issue(let issue) = result else {
                Issue.record("Expected transport issue")
                continue
            }
            #expect(issue == expected)
        }
    }

    @Test func existingGraphFeaturesStillLoad() async {
        let graph = StoreGraph(api: ShopAPIStub(reply: .payload([])))
        let results = [
            await graph.loadOrderSummary.execute(id: "123"),
            await graph.loadAccountName.execute(id: "123"),
            await graph.loadBasketName.execute(id: "123")
        ]
        for (result, expected) in zip(results, ["Order", "Account", "Basket"]) {
            guard case .value(let value) = result else {
                Issue.record("Expected existing feature value")
                continue
            }
            #expect(value == expected)
        }
    }
}

private final class ShopAPIStub: ShopAPI {
    let reply: TransportReply<[PickupLocationDTO]>
    private(set) var postcodes: [String] = []

    init(reply: TransportReply<[PickupLocationDTO]>) { self.reply = reply }

    func pickupLocations(postcode: String) async -> TransportReply<[PickupLocationDTO]> {
        postcodes.append(postcode)
        return reply
    }

    func orderSummary(id: String) async -> TransportReply<String> { .payload("Order") }
    func accountName(id: String) async -> TransportReply<String> { .payload("Account") }
    func basketName(id: String) async -> TransportReply<String> { .payload("Basket") }
    func shippingQuote(orderID: String) async -> TransportReply<ShippingQuoteDTO> { .failure(.offline) }
}
