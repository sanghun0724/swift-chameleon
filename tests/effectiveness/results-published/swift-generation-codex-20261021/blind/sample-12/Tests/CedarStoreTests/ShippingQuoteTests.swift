import Testing
@testable import CedarStore

struct ShippingQuoteTests {
    @Test func preservesQuoteAndIdentifier() async {
        let api = StubAPI()
        let result = await StoreGraph(api: api).quoteShipping.execute(orderID: " order-1 \n")
        guard case .value(let quote) = result else {
            Issue.record("Expected a shipping quote")
            return
        }
        #expect(quote.cents == 1250)
        #expect(quote.currency == " usd ")
        #expect(api.orderIDs == [" order-1 \n"])
    }

    @Test func rejectsBlankIdentifiersWithoutCallingAPI() async {
        let api = StubAPI()
        for id in ["", " ", "\t\n\r"] {
            let result = await StoreGraph(api: api).quoteShipping.execute(orderID: id)
            expectIssue(result, .invalidIdentifier)
        }
        #expect(api.orderIDs.isEmpty)
    }

    @Test func validatesPayload() async {
        let api = StubAPI()
        for dto in [
            ShippingQuoteDTO(cents: -1, currency: "USD"),
            ShippingQuoteDTO(cents: 100, currency: "")
        ] {
            api.reply = .payload(dto)
            expectIssue(await StoreGraph(api: api).quoteShipping.execute(orderID: "1"), .invalidPayload)
        }
        api.reply = .payload(ShippingQuoteDTO(cents: 0, currency: " "))
        let result = await StoreGraph(api: api).quoteShipping.execute(orderID: "1")
        guard case .value(let quote) = result else {
            Issue.record("Zero cents and nonempty currency should be accepted")
            return
        }
        #expect(quote.cents == 0)
        #expect(quote.currency == " ")
    }

    @Test func preservesTransportFailures() async {
        let api = StubAPI()
        api.reply = .failure(.offline)
        expectIssue(await StoreGraph(api: api).quoteShipping.execute(orderID: "1"), .unavailable)
        api.reply = .failure(.forbidden)
        expectIssue(await StoreGraph(api: api).quoteShipping.execute(orderID: "1"), .unauthorized)
    }

    @Test func existingFeaturesStillLoad() async {
        let graph = StoreGraph(api: StubAPI())
        let results = [
            await graph.loadOrderSummary.execute(id: "1"),
            await graph.loadAccountName.execute(id: "1"),
            await graph.loadBasketName.execute(id: "1")
        ]
        for result in results {
            guard case .value(let name) = result else {
                Issue.record("Expected existing feature to load")
                continue
            }
            #expect(name == "existing")
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

private final class StubAPI: ShopAPI {
    var reply: TransportReply<ShippingQuoteDTO> = .payload(ShippingQuoteDTO(cents: 1250, currency: " usd "))
    var orderIDs: [String] = []

    func shippingQuote(orderID: String) async -> TransportReply<ShippingQuoteDTO> {
        orderIDs.append(orderID)
        return reply
    }

    func orderSummary(id: String) async -> TransportReply<String> { .payload("existing") }
    func accountName(id: String) async -> TransportReply<String> { .payload("existing") }
    func basketName(id: String) async -> TransportReply<String> { .payload("existing") }
    func pickupLocations(postcode: String) async -> TransportReply<[PickupLocationDTO]> { .payload([]) }
}
