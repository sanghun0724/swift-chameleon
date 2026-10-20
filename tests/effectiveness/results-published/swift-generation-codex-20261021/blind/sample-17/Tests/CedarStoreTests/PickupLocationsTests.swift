import Testing
@testable import CedarStore

struct PickupLocationsTests {
    @Test func rejectsBlankPostcodesWithoutCallingAPI() async {
        let api = StubShopAPI()
        let graph = StoreGraph(api: api)

        for postcode in ["", " ", "\t\r\n", " \n\t "] {
            let result = await graph.loadPickupLocations.execute(postcode: postcode)
            guard case .issue(let issue) = result else {
                Issue.record("Expected invalidIdentifier")
                continue
            }
            #expect(issue == .invalidIdentifier)
        }
        #expect(api.postcodes.isEmpty)
    }

    @Test func forwardsPostcodeAndReturnsFirstEligibleLocationsInTitleAndIDOrder() async {
        let api = StubShopAPI()
        api.pickupReply = .payload([
            .init(id: "b", title: "Ignored inactive", capacity: 10, active: false),
            .init(id: "b", title: "Ignored negative", capacity: -1, active: true),
            .init(id: "z", title: "Zulu", capacity: 3, active: true),
            .init(id: "b", title: "Alpha", capacity: 0, active: true),
            .init(id: "b", title: "Aardvark duplicate", capacity: 9, active: true),
            .init(id: "a", title: "Alpha", capacity: 2, active: true),
            .init(id: "inactive", title: "Hidden", capacity: 1, active: false),
            .init(id: "negative", title: "Hidden", capacity: -1, active: true)
        ])

        let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: " AB12 \n")

        #expect(api.postcodes == [" AB12 \n"])
        guard case .value(let locations) = result else {
            Issue.record("Expected pickup locations")
            return
        }
        #expect(locations == [
            PickupLocation(id: "a", title: "Alpha", capacity: 2),
            PickupLocation(id: "b", title: "Alpha", capacity: 0),
            PickupLocation(id: "z", title: "Zulu", capacity: 3)
        ])
    }

    @Test func emptyAndIneligibleCatalogsReturnEmptySuccess() async {
        let api = StubShopAPI()
        for rows: [PickupLocationDTO] in [
            [],
            [.init(id: "a", title: "A", capacity: 0, active: false),
             .init(id: "b", title: "B", capacity: -1, active: true)]
        ] {
            api.pickupReply = .payload(rows)
            let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: "123")
            guard case .value(let locations) = result else {
                Issue.record("Expected empty success")
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
            let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: "123")
            guard case .issue(let issue) = result else {
                Issue.record("Expected mapped transport failure")
                continue
            }
            #expect(issue == expected)
        }
    }

    @Test func existingGraphFeaturesStillLoad() async {
        let api = StubShopAPI()
        let graph = StoreGraph(api: api)
        let results = [
            await graph.loadOrderSummary.execute(id: "order"),
            await graph.loadAccountName.execute(id: "account"),
            await graph.loadBasketName.execute(id: "basket")
        ]
        for (result, expected) in zip(results, ["order summary", "account name", "basket name"]) {
            guard case .value(let value) = result else {
                Issue.record("Expected existing feature value")
                continue
            }
            #expect(value == expected)
        }
        #expect(api.postcodes.isEmpty)
    }
}

private final class StubShopAPI: ShopAPI {
    var postcodes: [String] = []
    var pickupReply: TransportReply<[PickupLocationDTO]> = .payload([])

    func pickupLocations(postcode: String) async -> TransportReply<[PickupLocationDTO]> {
        postcodes.append(postcode)
        return pickupReply
    }

    func orderSummary(id: String) async -> TransportReply<String> { .payload("order summary") }
    func accountName(id: String) async -> TransportReply<String> { .payload("account name") }
    func basketName(id: String) async -> TransportReply<String> { .payload("basket name") }
    func shippingQuote(orderID: String) async -> TransportReply<ShippingQuoteDTO> {
        .payload(.init(cents: 0, currency: "USD"))
    }
}
