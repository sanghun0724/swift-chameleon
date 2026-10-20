import Testing
@testable import CedarStore

private final class StubShopAPI: ShopAPI {
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

@Test func preservesQuoteAndOrderID() async {
    let api = StubShopAPI()
    let graph = StoreGraph(api: api)
    for (cents, currency) in [(1250, "USD"), (0, " eur "), (42, " ")] {
        api.reply = .payload(.init(cents: cents, currency: currency))
        guard case .value(let quote) = await graph.quoteShipping.execute(orderID: " order-1 \n") else {
            Issue.record("Expected a valid quote")
            return
        }
        #expect(quote.cents == cents)
        #expect(quote.currency == currency)
    }
    #expect(api.orderIDs == Array(repeating: " order-1 \n", count: 3))
}

@Test func rejectsBlankIdentifiersWithoutCallingAPI() async {
    let api = StubShopAPI()
    for id in ["", " ", "\t\r\n", " \n\t "] {
        guard case .issue(let issue) = await StoreGraph(api: api).quoteShipping.execute(orderID: id) else {
            Issue.record("Expected invalid identifier")
            return
        }
        #expect(issue == .invalidIdentifier)
    }
    #expect(api.orderIDs.isEmpty)
}

@Test func rejectsInvalidPayloadsAndMapsTransportFailures() async {
    let cases: [(TransportReply<ShippingQuoteDTO>, ShopIssue)] = [
        (.payload(.init(cents: -1, currency: "USD")), .invalidPayload),
        (.payload(.init(cents: 10, currency: "")), .invalidPayload),
        (.failure(.offline), .unavailable),
        (.failure(.forbidden), .unauthorized),
    ]
    for (reply, expected) in cases {
        let api = StubShopAPI()
        api.reply = reply
        guard case .issue(let issue) = await StoreGraph(api: api).quoteShipping.execute(orderID: "order-1") else {
            Issue.record("Expected \(expected)")
            return
        }
        #expect(issue == expected)
        #expect(api.orderIDs == ["order-1"])
    }
}

@Test func existingGraphFeaturesStillLoad() async {
    let graph = StoreGraph(api: StubShopAPI())
    let results = [
        await graph.loadOrderSummary.execute(id: "1"),
        await graph.loadAccountName.execute(id: "1"),
        await graph.loadBasketName.execute(id: "1"),
    ]
    for (result, expected) in zip(results, ["Order", "Account", "Basket"]) {
        guard case .value(let value) = result else {
            Issue.record("Expected \(expected)")
            continue
        }
        #expect(value == expected)
    }
}
