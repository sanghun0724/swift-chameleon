import Testing
@testable import CedarStore

@Test func rejectsBlankOrderIDsWithoutCallingAPI() async {
    let api = StubShopAPI()
    let graph = StoreGraph(api: api)
    for id in ["", " ", "\t\r\n", " \n\t "] {
        expectIssue(await graph.quoteShipping.execute(orderID: id), .invalidIdentifier)
    }
    #expect(api.shippingOrderIDs.isEmpty)
}

@Test func preservesOrderIDAndQuoteValues() async {
    let api = StubShopAPI()
    let graph = StoreGraph(api: api)
    for cents in [0, 12345, Int.max] {
        api.quoteReply = .payload(ShippingQuoteDTO(cents: cents, currency: " uSd "))
        let result = await graph.quoteShipping.execute(orderID: " \torder-123\n")
        guard case .value(let quote) = result else {
            Issue.record("Expected shipping quote")
            return
        }
        #expect(quote.cents == cents)
        #expect(quote.currency == " uSd ")
    }
    #expect(api.shippingOrderIDs == Array(repeating: " \torder-123\n", count: 3))
}

@Test func rejectsInvalidQuotePayloads() async {
    let api = StubShopAPI()
    let graph = StoreGraph(api: api)
    for dto in [
        ShippingQuoteDTO(cents: -1, currency: "USD"),
        ShippingQuoteDTO(cents: 100, currency: ""),
    ] {
        api.quoteReply = .payload(dto)
        expectIssue(await graph.quoteShipping.execute(orderID: "order"), .invalidPayload)
    }
}

@Test func preservesTransportFailureMapping() async {
    let api = StubShopAPI()
    let graph = StoreGraph(api: api)
    for (transport, expected) in [
        (TransportIssue.offline, ShopIssue.unavailable),
        (.forbidden, .unauthorized),
    ] {
        api.quoteReply = .failure(transport)
        expectIssue(await graph.quoteShipping.execute(orderID: "order"), expected)
    }
}

@Test func existingFeaturesStillLoadAndValidate() async {
    let api = StubShopAPI()
    let graph = StoreGraph(api: api)
    expectValue(await graph.loadOrderSummary.execute(id: "order"), "summary")
    expectValue(await graph.loadAccountName.execute(id: "account"), "account")
    expectValue(await graph.loadBasketName.execute(id: "basket"), "basket")
    expectIssue(await graph.loadOrderSummary.execute(id: " "), .invalidIdentifier)
    expectIssue(await graph.loadAccountName.execute(id: "\n"), .invalidIdentifier)
    expectIssue(await graph.loadBasketName.execute(id: ""), .invalidIdentifier)
    #expect(api.shippingOrderIDs.isEmpty)
}

private func expectIssue<T>(_ result: ShopResult<T>, _ expected: ShopIssue) {
    guard case .issue(let issue) = result else {
        Issue.record("Expected issue \(expected)")
        return
    }
    #expect(issue == expected)
}

private func expectValue(_ result: ShopResult<String>, _ expected: String) {
    guard case .value(let value) = result else {
        Issue.record("Expected value \(expected)")
        return
    }
    #expect(value == expected)
}

private final class StubShopAPI: ShopAPI {
    var shippingOrderIDs: [String] = []
    var quoteReply: TransportReply<ShippingQuoteDTO> =
        .payload(ShippingQuoteDTO(cents: 500, currency: "USD"))

    func shippingQuote(orderID: String) async -> TransportReply<ShippingQuoteDTO> {
        shippingOrderIDs.append(orderID)
        return quoteReply
    }

    func orderSummary(id: String) async -> TransportReply<String> { .payload("summary") }
    func accountName(id: String) async -> TransportReply<String> { .payload("account") }
    func basketName(id: String) async -> TransportReply<String> { .payload("basket") }
    func pickupLocations(postcode: String) async -> TransportReply<[PickupLocationDTO]> {
        .payload([])
    }
}
