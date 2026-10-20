import Testing
@testable import CedarStore

@Test func quotesPreserveValuesAndOrderID() async {
    for cents in [0, 1299, Int.max] {
        let api = ShopAPIStub()
        api.shippingReply = .payload(ShippingQuoteDTO(cents: cents, currency: " uSd "))
        let result = await StoreGraph(api: api).quoteShipping.execute(orderID: " order-1 \n")
        guard case .value(let quote) = result else {
            Issue.record("Expected a shipping quote")
            return
        }
        #expect(quote.cents == cents)
        #expect(quote.currency == " uSd ")
        #expect(api.shippingOrderIDs == [" order-1 \n"])
    }
}

@Test func blankIdentifiersNeverCallAPI() async {
    let api = ShopAPIStub()
    for id in ["", " ", "\t\r\n", "\u{2003}"] {
        let result = await StoreGraph(api: api).quoteShipping.execute(orderID: id)
        expectIssue(result, .invalidIdentifier)
    }
    #expect(api.shippingOrderIDs.isEmpty)
}

@Test func invalidQuotesAreRejected() async {
    for dto in [
        ShippingQuoteDTO(cents: -1, currency: "USD"),
        ShippingQuoteDTO(cents: 100, currency: "")
    ] {
        let api = ShopAPIStub()
        api.shippingReply = .payload(dto)
        expectIssue(await StoreGraph(api: api).quoteShipping.execute(orderID: "order"), .invalidPayload)
    }
}

@Test func transportFailuresKeepTheirMapping() async {
    for (transport, issue) in [(TransportIssue.offline, ShopIssue.unavailable), (.forbidden, .unauthorized)] {
        let api = ShopAPIStub()
        api.shippingReply = .failure(transport)
        expectIssue(await StoreGraph(api: api).quoteShipping.execute(orderID: "order"), issue)
    }
}

@Test func existingFeaturesKeepTheirBehavior() async {
    let api = ShopAPIStub()
    let graph = StoreGraph(api: api)
    expectValue(await graph.loadOrderSummary.execute(id: "order"), "existing")
    expectValue(await graph.loadAccountName.execute(id: "account"), "existing")
    expectValue(await graph.loadBasketName.execute(id: "basket"), "existing")
    expectIssue(await graph.loadOrderSummary.execute(id: " "), .invalidIdentifier)
    expectIssue(await graph.loadAccountName.execute(id: ""), .invalidIdentifier)
    expectIssue(await graph.loadBasketName.execute(id: "\n"), .invalidIdentifier)
    api.nameReply = .payload("")
    expectIssue(await graph.loadOrderSummary.execute(id: "order"), .invalidPayload)
    expectIssue(await graph.loadAccountName.execute(id: "account"), .invalidPayload)
    expectIssue(await graph.loadBasketName.execute(id: "basket"), .invalidPayload)
    for (transport, issue) in [(TransportIssue.offline, ShopIssue.unavailable), (.forbidden, .unauthorized)] {
        api.nameReply = .failure(transport)
        expectIssue(await graph.loadOrderSummary.execute(id: "order"), issue)
        expectIssue(await graph.loadAccountName.execute(id: "account"), issue)
        expectIssue(await graph.loadBasketName.execute(id: "basket"), issue)
    }
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

private final class ShopAPIStub: ShopAPI {
    var shippingReply: TransportReply<ShippingQuoteDTO> = .payload(.init(cents: 500, currency: "USD"))
    var nameReply: TransportReply<String> = .payload("existing")
    var shippingOrderIDs: [String] = []

    func shippingQuote(orderID: String) async -> TransportReply<ShippingQuoteDTO> {
        shippingOrderIDs.append(orderID)
        return shippingReply
    }

    func orderSummary(id: String) async -> TransportReply<String> { nameReply }
    func accountName(id: String) async -> TransportReply<String> { nameReply }
    func basketName(id: String) async -> TransportReply<String> { nameReply }
    func pickupLocations(postcode: String) async -> TransportReply<[PickupLocationDTO]> { .payload([]) }
}
