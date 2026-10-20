import Testing
@testable import CedarStore

struct ShippingQuoteTests {
    @Test func preservesQuoteAndIdentifier() async {
        for cents in [0, 1299] {
            let api = StubAPI(reply: .payload(ShippingQuoteDTO(cents: cents, currency: " USD ")))
            let result = await StoreGraph(api: api).quoteShipping.execute(orderID: " order-1 \n")
            guard case .value(let quote) = result else {
                Issue.record("Expected a shipping quote")
                return
            }
            #expect(quote.cents == cents)
            #expect(quote.currency == " USD ")
            #expect(api.orderIDs == [" order-1 \n"])
        }
    }

    @Test func rejectsBlankIdentifiersWithoutCallingAPI() async {
        let api = StubAPI(reply: .failure(.offline))
        for id in ["", " ", "\t\n\r"] {
            let result = await StoreGraph(api: api).quoteShipping.execute(orderID: id)
            expectIssue(result, .invalidIdentifier)
        }
        #expect(api.orderIDs.isEmpty)
    }

    @Test func rejectsInvalidPayloads() async {
        for dto in [
            ShippingQuoteDTO(cents: -1, currency: "USD"),
            ShippingQuoteDTO(cents: 100, currency: "")
        ] {
            let api = StubAPI(reply: .payload(dto))
            expectIssue(await StoreGraph(api: api).quoteShipping.execute(orderID: "order"), .invalidPayload)
        }
    }

    @Test func mapsTransportFailures() async {
        for (failure, expected) in [
            (TransportIssue.offline, ShopIssue.unavailable),
            (.forbidden, .unauthorized)
        ] {
            let api = StubAPI(reply: .failure(failure))
            expectIssue(await StoreGraph(api: api).quoteShipping.execute(orderID: "order"), expected)
        }
    }

    @Test func existingGraphFeaturesStillLoad() async {
        let graph = StoreGraph(api: StubAPI(reply: .failure(.offline)))
        let results = [
            await graph.loadOrderSummary.execute(id: "order"),
            await graph.loadAccountName.execute(id: "account"),
            await graph.loadBasketName.execute(id: "basket")
        ]
        for result in results {
            guard case .value(let value) = result else {
                Issue.record("Expected existing feature to load")
                continue
            }
            #expect(value == "existing")
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
    let reply: TransportReply<ShippingQuoteDTO>
    var orderIDs: [String] = []

    init(reply: TransportReply<ShippingQuoteDTO>) { self.reply = reply }

    func shippingQuote(orderID: String) async -> TransportReply<ShippingQuoteDTO> {
        orderIDs.append(orderID)
        return reply
    }

    func orderSummary(id: String) async -> TransportReply<String> { .payload("existing") }
    func accountName(id: String) async -> TransportReply<String> { .payload("existing") }
    func basketName(id: String) async -> TransportReply<String> { .payload("existing") }
    func pickupLocations(postcode: String) async -> TransportReply<[PickupLocationDTO]> { .payload([]) }
}
