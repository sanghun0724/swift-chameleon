import Testing
@testable import CedarStore

struct PickupLocationsTests {
    @Test func filtersDeduplicatesAndSortsLocations() async {
        let api = StubShopAPI(reply: .payload([
            .init(id: "b", title: "Ignored", capacity: 10, active: false),
            .init(id: "b", title: "Ignored", capacity: -1, active: true),
            .init(id: "z", title: "Zulu", capacity: 1, active: true),
            .init(id: "b", title: "Alpha", capacity: 0, active: true),
            .init(id: "a", title: "Alpha", capacity: 2, active: true),
            .init(id: "b", title: "Duplicate", capacity: 9, active: true)
        ]))

        let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: "  AB12 \n")

        expectValue(result, [
            PickupLocation(id: "a", title: "Alpha", capacity: 2),
            PickupLocation(id: "b", title: "Alpha", capacity: 0),
            PickupLocation(id: "z", title: "Zulu", capacity: 1)
        ])
        #expect(api.postcodes == ["  AB12 \n"])
    }

    @Test func rejectsBlankPostcodesWithoutCallingAPI() async {
        let api = StubShopAPI(reply: .payload([]))
        for postcode in ["", " ", "\t\r\n", "\u{2003}"] {
            let result = await StoreGraph(api: api).loadPickupLocations.execute(postcode: postcode)
            expectIssue(result, .invalidIdentifier)
        }
        #expect(api.postcodes.isEmpty)
    }

    @Test func acceptsEmptyCatalogs() async {
        for rows: [PickupLocationDTO] in [
            [],
            [.init(id: "a", title: "A", capacity: -1, active: true),
             .init(id: "b", title: "B", capacity: 1, active: false)]
        ] {
            let api = StubShopAPI(reply: .payload(rows))
            expectValue(await StoreGraph(api: api).loadPickupLocations.execute(postcode: "123"), [])
        }
    }

    @Test func mapsTransportFailures() async {
        let offline = StubShopAPI(reply: .failure(.offline))
        expectIssue(await StoreGraph(api: offline).loadPickupLocations.execute(postcode: "123"), .unavailable)
        let forbidden = StubShopAPI(reply: .failure(.forbidden))
        expectIssue(await StoreGraph(api: forbidden).loadPickupLocations.execute(postcode: "123"), .unauthorized)
    }

    @Test func existingGraphFeaturesStillLoad() async {
        let graph = StoreGraph(api: StubShopAPI(reply: .payload([])))
        expectValue(await graph.loadOrderSummary.execute(id: "1"), "Order")
        expectValue(await graph.loadAccountName.execute(id: "1"), "Account")
        expectValue(await graph.loadBasketName.execute(id: "1"), "Basket")
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
    let reply: TransportReply<[PickupLocationDTO]>
    var postcodes: [String] = []

    init(reply: TransportReply<[PickupLocationDTO]>) { self.reply = reply }

    func pickupLocations(postcode: String) async -> TransportReply<[PickupLocationDTO]> {
        postcodes.append(postcode)
        return reply
    }

    func orderSummary(id: String) async -> TransportReply<String> { .payload("Order") }
    func accountName(id: String) async -> TransportReply<String> { .payload("Account") }
    func basketName(id: String) async -> TransportReply<String> { .payload("Basket") }
    func shippingQuote(orderID: String) async -> TransportReply<ShippingQuoteDTO> {
        .payload(.init(cents: 0, currency: "USD"))
    }
}
