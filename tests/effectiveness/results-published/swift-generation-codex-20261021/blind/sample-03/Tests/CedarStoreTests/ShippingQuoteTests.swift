import Testing
@testable import CedarStore

private final class StubShopAPI: ShopAPI {
    var shippingReply: TransportReply<ShippingQuoteDTO> = .payload(
        ShippingQuoteDTO(cents: 1234, currency: "USD")
    )
    var shippingOrderIDs: [String] = []
    var nameReply: TransportReply<String> = .payload("Name")
    var nameIDs: [String] = []

    func shippingQuote(orderID: String) async -> TransportReply<ShippingQuoteDTO> {
        shippingOrderIDs.append(orderID)
        return shippingReply
    }

    func orderSummary(id: String) async -> TransportReply<String> {
        nameIDs.append(id)
        return nameReply
    }

    func accountName(id: String) async -> TransportReply<String> {
        nameIDs.append(id)
        return nameReply
    }

    func basketName(id: String) async -> TransportReply<String> {
        nameIDs.append(id)
        return nameReply
    }

    func pickupLocations(postcode: String) async -> TransportReply<[PickupLocationDTO]> {
        .payload([])
    }
}

private func expectIssue<T>(_ result: ShopResult<T>, _ expected: ShopIssue) {
    guard case .issue(let issue) = result else {
        Issue.record("Expected issue \(expected)")
        return
    }
    #expect(issue == expected)
}

@Test func shippingPreservesPayloadAndIdentifier() async {
    for cents in [0, 1234, Int.max] {
        let api = StubShopAPI()
        api.shippingReply = .payload(ShippingQuoteDTO(cents: cents, currency: " eur "))
        let result = await StoreGraph(api: api).quoteShipping.execute(orderID: " \torder-1\n")
        guard case .value(let quote) = result else {
            Issue.record("Expected shipping quote")
            continue
        }
        #expect(quote.cents == cents)
        #expect(quote.currency == " eur ")
        #expect(api.shippingOrderIDs == [" \torder-1\n"])
    }
}

@Test func shippingRejectsBlankIdentifiersWithoutAPICalls() async {
    let api = StubShopAPI()
    let graph = StoreGraph(api: api)
    for id in ["", " ", "\t\n\r", "\u{2003}"] {
        expectIssue(await graph.quoteShipping.execute(orderID: id), .invalidIdentifier)
    }
    #expect(api.shippingOrderIDs.isEmpty)
}

@Test func shippingRejectsInvalidPayloads() async {
    for dto in [
        ShippingQuoteDTO(cents: -1, currency: "USD"),
        ShippingQuoteDTO(cents: 100, currency: ""),
    ] {
        let api = StubShopAPI()
        api.shippingReply = .payload(dto)
        expectIssue(
            await StoreGraph(api: api).quoteShipping.execute(orderID: "order-1"),
            .invalidPayload
        )
    }
}

@Test func shippingMapsTransportFailures() async {
    for (transport, expected) in [
        (TransportIssue.offline, ShopIssue.unavailable),
        (.forbidden, .unauthorized),
    ] {
        let api = StubShopAPI()
        api.shippingReply = .failure(transport)
        expectIssue(
            await StoreGraph(api: api).quoteShipping.execute(orderID: "order-1"),
            expected
        )
        #expect(api.shippingOrderIDs == ["order-1"])
    }
}

@Test func existingFeaturesRetainValidationAndMapping() async {
    let api = StubShopAPI()
    let graph = StoreGraph(api: api)
    for feature in 0..<3 {
        func execute(_ id: String) async -> ShopResult<String> {
            switch feature {
            case 0: return await graph.loadOrderSummary.execute(id: id)
            case 1: return await graph.loadAccountName.execute(id: id)
            default: return await graph.loadBasketName.execute(id: id)
            }
        }

        api.nameIDs = []
        expectIssue(await execute(" \n"), .invalidIdentifier)
        #expect(api.nameIDs.isEmpty)

        api.nameReply = .payload("Name")
        if case .value(let name) = await execute(" id ") {
            #expect(name == "Name")
        } else {
            Issue.record("Expected name")
        }
        #expect(api.nameIDs == [" id "])

        api.nameReply = .payload("")
        expectIssue(await execute("id"), .invalidPayload)
        api.nameReply = .failure(.offline)
        expectIssue(await execute("id"), .unavailable)
        api.nameReply = .failure(.forbidden)
        expectIssue(await execute("id"), .unauthorized)
    }
}
