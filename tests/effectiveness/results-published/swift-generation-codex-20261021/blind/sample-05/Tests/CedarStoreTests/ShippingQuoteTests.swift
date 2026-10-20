import Testing
@testable import CedarStore

struct ShippingQuoteTests {
    @Test func preservesQuoteAndIdentifier() async {
        for cents in [0, 12345, Int.max] {
            let api = ShopAPIStub(reply: .payload(.init(cents: cents, currency: " usd ")))
            let result = await StoreGraph(api: api).quoteShipping.execute(orderID: " order-1 \n")
            guard case .value(let quote) = result else {
                Issue.record("Expected a shipping quote")
                return
            }
            #expect(quote.cents == cents)
            #expect(quote.currency == " usd ")
            #expect(api.shippingOrderIDs == [" order-1 \n"])
        }
    }

    @Test func rejectsBlankIdentifiersWithoutCallingAPI() async {
        for id in ["", " ", "\t\r\n", "\u{2003}"] {
            let api = ShopAPIStub()
            let result = await StoreGraph(api: api).quoteShipping.execute(orderID: id)
            expectIssue(result, .invalidIdentifier)
            #expect(api.shippingOrderIDs.isEmpty)
        }
    }

    @Test func rejectsInvalidPayloads() async {
        for dto in [
            ShippingQuoteDTO(cents: -1, currency: "USD"),
            ShippingQuoteDTO(cents: 100, currency: ""),
        ] {
            let api = ShopAPIStub(reply: .payload(dto))
            expectIssue(
                await StoreGraph(api: api).quoteShipping.execute(orderID: "order-1"),
                .invalidPayload
            )
        }
    }

    @Test func mapsTransportFailures() async {
        for (transport, expected) in [
            (TransportIssue.offline, ShopIssue.unavailable),
            (.forbidden, .unauthorized),
        ] {
            let api = ShopAPIStub(reply: .failure(transport))
            expectIssue(
                await StoreGraph(api: api).quoteShipping.execute(orderID: "order-1"),
                expected
            )
        }
    }

    @Test func existingGraphFeaturesStillWork() async {
        let graph = StoreGraph(api: ShopAPIStub())
        let results = [
            await graph.loadOrderSummary.execute(id: "order-1"),
            await graph.loadAccountName.execute(id: "account-1"),
            await graph.loadBasketName.execute(id: "basket-1"),
        ]
        for (result, expected) in zip(results, ["summary", "account", "basket"]) {
            guard case .value(let value) = result else {
                Issue.record("Expected existing feature to succeed")
                continue
            }
            #expect(value == expected)
        }
    }

    private func expectIssue<T>(_ result: ShopResult<T>, _ expected: ShopIssue) {
        guard case .issue(let issue) = result else {
            Issue.record("Expected \(expected)")
            return
        }
        #expect(issue == expected)
    }
}

private final class ShopAPIStub: ShopAPI {
    var shippingOrderIDs: [String] = []
    let reply: TransportReply<ShippingQuoteDTO>

    init(reply: TransportReply<ShippingQuoteDTO> = .payload(.init(cents: 100, currency: "USD"))) {
        self.reply = reply
    }

    func shippingQuote(orderID: String) async -> TransportReply<ShippingQuoteDTO> {
        shippingOrderIDs.append(orderID)
        return reply
    }

    func orderSummary(id: String) async -> TransportReply<String> { .payload("summary") }
    func accountName(id: String) async -> TransportReply<String> { .payload("account") }
    func basketName(id: String) async -> TransportReply<String> { .payload("basket") }
    func pickupLocations(postcode: String) async -> TransportReply<[PickupLocationDTO]> { .payload([]) }
}
