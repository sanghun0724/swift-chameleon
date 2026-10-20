import Testing
@testable import CedarStore

private final class APIStub: ShopAPI {
    var reply: TransportReply<ShippingQuoteDTO> = .payload(.init(cents: 1299, currency: "USD"))
    var shippingIDs: [String] = []

    func shippingQuote(orderID: String) async -> TransportReply<ShippingQuoteDTO> {
        shippingIDs.append(orderID)
        return reply
    }

    func orderSummary(id: String) async -> TransportReply<String> { .payload("Order") }
    func accountName(id: String) async -> TransportReply<String> { .payload("Account") }
    func basketName(id: String) async -> TransportReply<String> { .payload("Basket") }
    func pickupLocations(postcode: String) async -> TransportReply<[PickupLocationDTO]> { .payload([]) }
}

@Test func shippingPreservesValuesAndIdentifier() async {
    let api = APIStub()
    let graph = StoreGraph(api: api)
    for cents in [0, 1299, Int.max] {
        api.reply = .payload(.init(cents: cents, currency: " usd "))
        let result = await graph.quoteShipping.execute(orderID: " order-1 \n")
        guard case .value(let quote) = result else {
            Issue.record("Expected shipping quote")
            return
        }
        #expect(quote.cents == cents)
        #expect(quote.currency == " usd ")
    }
    #expect(api.shippingIDs == Array(repeating: " order-1 \n", count: 3))
}

@Test func blankIdentifiersNeverCallAPI() async {
    let api = APIStub()
    for id in ["", " ", "\t\n\r", "\u{2003}"] {
        let result = await StoreGraph(api: api).quoteShipping.execute(orderID: id)
        guard case .issue(.invalidIdentifier) = result else {
            Issue.record("Expected invalidIdentifier")
            continue
        }
    }
    #expect(api.shippingIDs.isEmpty)
}

@Test func invalidShippingPayloads() async {
    let api = APIStub()
    for dto in [ShippingQuoteDTO(cents: -1, currency: "USD"),
                ShippingQuoteDTO(cents: 100, currency: "")] {
        api.reply = .payload(dto)
        let result = await StoreGraph(api: api).quoteShipping.execute(orderID: "order")
        guard case .issue(.invalidPayload) = result else {
            Issue.record("Expected invalidPayload")
            continue
        }
    }
}

@Test func shippingTransportFailures() async {
    let api = APIStub()
    for (transport, expected) in [(TransportIssue.offline, ShopIssue.unavailable),
                                  (.forbidden, .unauthorized)] {
        api.reply = .failure(transport)
        let result = await StoreGraph(api: api).quoteShipping.execute(orderID: "order")
        guard case .issue(let issue) = result else {
            Issue.record("Expected transport issue")
            continue
        }
        #expect(issue == expected)
    }
}

@Test func existingGraphFeaturesStillLoad() async {
    let graph = StoreGraph(api: APIStub())
    let results = [
        await graph.loadOrderSummary.execute(id: "order"),
        await graph.loadAccountName.execute(id: "account"),
        await graph.loadBasketName.execute(id: "basket"),
    ]
    for (result, expected) in zip(results, ["Order", "Account", "Basket"]) {
        guard case .value(let value) = result else {
            Issue.record("Expected existing feature value")
            continue
        }
        #expect(value == expected)
    }
}
