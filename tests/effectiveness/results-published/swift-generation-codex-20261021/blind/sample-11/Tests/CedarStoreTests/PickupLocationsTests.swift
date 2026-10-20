import Testing
@testable import CedarStore

struct PickupLocationsTests {
    @Test func filtersDeduplicatesSortsAndForwardsPostcode() async {
        let api = ShopAPIStub()
        api.pickupReply = .payload([
            .init(id: "b", title: "Ignored inactive", capacity: 1, active: false),
            .init(id: "b", title: "Ignored negative", capacity: -1, active: true),
            .init(id: "b", title: "Alpha", capacity: 0, active: true),
            .init(id: "b", title: "Duplicate", capacity: 10, active: true),
            .init(id: "z", title: "Zulu", capacity: 2, active: true),
            .init(id: "a", title: "Alpha", capacity: 3, active: true)
        ])

        let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: " AB12 \n")

        guard case .value(let locations) = result else {
            Issue.record("Expected pickup locations")
            return
        }
        #expect(locations == [
            PickupLocation(id: "a", title: "Alpha", capacity: 3),
            PickupLocation(id: "b", title: "Alpha", capacity: 0),
            PickupLocation(id: "z", title: "Zulu", capacity: 2)
        ])
        #expect(api.postcodes == [" AB12 \n"])
    }

    @Test func blankPostcodesSkipAPI() async {
        let api = ShopAPIStub()
        for postcode in ["", " \t\r\n", "\u{00A0}"] {
            let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: postcode)
            guard case .issue(let issue) = result else {
                Issue.record("Expected invalid identifier")
                continue
            }
            #expect(issue == .invalidIdentifier)
        }
        #expect(api.postcodes.isEmpty)
    }

    @Test func transportFailuresKeepDomainMapping() async {
        let api = ShopAPIStub()
        for (failure, expected) in [(TransportIssue.offline, ShopIssue.unavailable), (.forbidden, .unauthorized)] {
            api.pickupReply = .failure(failure)
            let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: "AB12")
            guard case .issue(let issue) = result else {
                Issue.record("Expected transport issue")
                continue
            }
            #expect(issue == expected)
        }
    }

    @Test func emptyAndIneligibleCatalogsSucceed() async {
        let api = ShopAPIStub()
        for rows: [PickupLocationDTO] in [[], [
            .init(id: "a", title: "Inactive", capacity: 1, active: false),
            .init(id: "b", title: "Negative", capacity: -1, active: true)
        ]] {
            api.pickupReply = .payload(rows)
            let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: "AB12")
            guard case .value(let locations) = result else {
                Issue.record("Expected empty success")
                continue
            }
            #expect(locations.isEmpty)
        }
    }

    @Test func existingGraphFeaturesStillLoad() async {
        let graph = StoreGraph(api: ShopAPIStub())
        let results = [
            await graph.loadOrderSummary.execute(id: "order"),
            await graph.loadAccountName.execute(id: "account"),
            await graph.loadBasketName.execute(id: "basket")
        ]
        for result in results {
            guard case .value(let value) = result else {
                Issue.record("Expected existing feature success")
                continue
            }
            #expect(value == "Existing value")
        }
    }
}

private final class ShopAPIStub: ShopAPI {
    var pickupReply: TransportReply<[PickupLocationDTO]> = .payload([])
    var postcodes: [String] = []

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
