import Testing
@testable import CedarStore

private final class StubAPI: ShopAPI {
    var reply: TransportReply<ShippingQuoteDTO> = .payload(.init(cents: 1250, currency: "USD"))
    var orderIDs: [String] = []

    func shippingQuote(orderID: String) async -> TransportReply<ShippingQuoteDTO> {
        orderIDs.append(orderID)
        return reply
    }

    func orderSummary(id: String) async -> TransportReply<String> { .payload("Order") }
    func accountName(id: String) async -> TransportReply<String> { .payload("Account") }
    func basketName(id: String) async -> TransportReply<String> { .payload("Basket") }
    func pickupLocations(postcode: String) async -> TransportReply<[PickupLocationDTO]> { .payload([]) }
}

private func expectIssue<T>(_ result: ShopResult<T>, _ expected: ShopIssue) {
    guard case .issue(let issue) = result else {
        Issue.record("Expected \(expected)")
        return
    }
    #expect(issue == expected)
}

@Test func preservesQuoteAndOriginalIdentifier() async {
    let api = StubAPI()
    let graph = StoreGraph(api: api)
    for cents in [0, 1250] {
        api.reply = .payload(.init(cents: cents, currency: " usd "))
        let result = await graph.quoteShipping.execute(orderID: " order-1 \n")
        guard case .value(let quote) = result else {
            Issue.record("Expected a quote")
            return
        }
        #expect(quote.cents == cents)
        #expect(quote.currency == " usd ")
    }
    #expect(api.orderIDs == [" order-1 \n", " order-1 \n"])
}

@Test func rejectsBlankIdentifiersWithoutCallingAPI() async {
    let api = StubAPI()
    let graph = StoreGraph(api: api)
    for id in ["", " ", "\t\n\r"] {
        expectIssue(await graph.quoteShipping.execute(orderID: id), .invalidIdentifier)
    }
    #expect(api.orderIDs.isEmpty)
}

@Test func rejectsInvalidPayloads() async {
    let api = StubAPI()
    let graph = StoreGraph(api: api)
    for dto in [ShippingQuoteDTO(cents: -1, currency: "USD"), ShippingQuoteDTO(cents: 100, currency: "")] {
        api.reply = .payload(dto)
        expectIssue(await graph.quoteShipping.execute(orderID: "order-1"), .invalidPayload)
    }
}

@Test func mapsTransportFailures() async {
    let api = StubAPI()
    let graph = StoreGraph(api: api)
    api.reply = .failure(.offline)
    expectIssue(await graph.quoteShipping.execute(orderID: "order-1"), .unavailable)
    api.reply = .failure(.forbidden)
    expectIssue(await graph.quoteShipping.execute(orderID: "order-1"), .unauthorized)
}

@Test func existingGraphFeaturesStillLoad() async {
    let graph = StoreGraph(api: StubAPI())
    let results = [
        (await graph.loadOrderSummary.execute(id: "1"), "Order"),
        (await graph.loadAccountName.execute(id: "1"), "Account"),
        (await graph.loadBasketName.execute(id: "1"), "Basket")
    ]
    for (result, expected) in results {
        guard case .value(let value) = result else {
            Issue.record("Expected \(expected)")
            continue
        }
        #expect(value == expected)
    }
}
